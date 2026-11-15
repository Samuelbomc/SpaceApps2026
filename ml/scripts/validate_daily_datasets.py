"""Verify daily labels, every lead pair and current inference inputs; no training."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.datasets.daily import materialize
from ml.scripts import prepare_expanded_datasets as source
from ml.scripts.prepare_daily_datasets import features_for_point, target_calendar


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/prepared/daily"))
    args = parser.parse_args()
    manifest = json.loads((args.root / "manifest.json").read_text())
    source.discover_index(manifest["issue_date"])
    pp, powers, _ = source.load_power()
    sp, sm, sm_counts, sm_errors, _ = source.load_moisture()
    rain, _ = source.load_rain(pp + sp)
    report = {
        "status": "PASS",
        "models_trained": False,
        "issue_date": manifest["issue_date"],
        "models": {},
    }
    for name, spec in manifest["models"].items():
        folder = args.root / name
        f = pd.read_csv(folder / "features.csv")
        labels = pd.read_csv(folder / "labels.csv")
        inference = pd.read_csv(folder / "inference.csv")
        assert np.array_equal(f.feature_id, np.arange(len(f)))
        assert np.array_equal(labels.label_id, np.arange(len(labels)))
        assert np.isfinite(f[spec["base_features"]].to_numpy(float)).all()
        assert np.isfinite(labels.target).all()
        assert np.isfinite(inference[spec["features"]].to_numpy(float)).all()
        assert "target" not in inference
        assert not f.duplicated(["point_id", "issue_date"]).any()
        assert not labels.duplicated(["point_id", "target_date"]).any()
        assert not inference.duplicated(["point_id", "lead_days"]).any()
        assert set(inference.issue_date) == {manifest["issue_date"]}
        assert set(inference.lead_days) == set(range(1, 61))
        assert (inference.groupby("point_id").size() == 60).all()
        for table in (f, inference):
            issue = pd.to_datetime(table.issue_date)
            assert ((issue - pd.to_datetime(table.observation_cutoff)).dt.days == 2).all()
            assert ((issue - pd.to_datetime(table.radiation_observation_cutoff)).dt.days == 7).all()
        assert (
            (pd.to_datetime(inference.target_date) - pd.to_datetime(inference.issue_date)).dt.days
            == inference.lead_days
        ).all()
        for col, values in target_calendar(pd.to_datetime(inference.target_date)).items():
            np.testing.assert_allclose(inference[col], values)
        # Every daily target is reconstructed from the screened raw observations.
        point_nums = labels.point_id.str.rsplit("_", n=1).str[-1].astype(int).to_numpy()
        days = source.INDEX.get_indexer(pd.to_datetime(labels.target_date))
        assert (days >= 0).all()
        if name.startswith("temperature"):
            col = {
                "temperature_mean": "T2M",
                "temperature_min": "T2M_MIN",
                "temperature_max": "T2M_MAX",
            }[name]
            raw = np.column_stack([p[col].to_numpy() for p in powers])
        elif name == "precipitation":
            raw = rain.iloc[:, : len(pp)].to_numpy()
        else:
            raw = sm.to_numpy()
            assert f.smap_age_days.between(0, 14).all()
            for col, values in (
                ("retrieval_count", sm_counts),
                ("recommended_retrieval_count", sm.attrs["recommended_counts"]),
                ("uncertainty_available_count", sm_errors),
            ):
                np.testing.assert_allclose(labels[col], values.to_numpy()[days, point_nums])
        np.testing.assert_allclose(labels.target, raw[days, point_nums])
        fdates = f.issue_date.to_numpy(dtype="datetime64[D]")
        ldates = labels.target_date.to_numpy(dtype="datetime64[D]")
        fp, lp = f.point_id.to_numpy(), labels.point_id.to_numpy()
        total = 0
        for lead in range(1, 61):
            with np.load(folder / "pairs" / f"lead_{lead:02d}.npz") as pair:
                fi, li = pair["feature_id"], pair["label_id"]
                assert len(fi) == spec["training_pairs_by_lead"][str(lead)] and len(fi) == len(li)
                assert ((fi >= 0) & (fi < len(f))).all() and ((li >= 0) & (li < len(labels))).all()
                assert len(np.unique(li)) == len(li)
                assert np.array_equal(fp[fi], lp[li])
                assert ((ldates[li] - fdates[fi]).astype(int) == lead).all()
                sample = np.unique([0, len(fi) // 2, len(fi) - 1])
                batch = materialize(f, labels, fi[sample], li[sample], lead)
                assert np.isfinite(batch[spec["features"] + ["target"]].to_numpy(float)).all()
                total += len(fi)
        # Recompute every current location from raw weather history and show
        # that perturbing future measurements cannot alter these predictors.
        for row in inference[inference.lead_days == 1].itertuples():
            p = int(row.point_id.rsplit("_", 1)[-1])
            if name == "moisture":
                nearest = int(np.argmin(np.sum((np.array(pp) - sp[p]) ** 2, axis=1)))
                r = rain[len(pp) + p].copy()
                available = sm[p].loc[: row.observation_cutoff]
                last = available.last_valid_index()
                assert np.isclose(available.dropna().iloc[-1], row.smap_last_valid_m3_m3)
                assert (pd.Timestamp(row.observation_cutoff) - last).days == row.smap_age_days
                week = available.loc[pd.Timestamp(row.observation_cutoff) - pd.Timedelta(days=6) :]
                expected_baseline = (
                    week.mean() if week.notna().any() else available.dropna().iloc[-1]
                )
                assert np.isclose(expected_baseline, row.smap_mean_7d)
            else:
                nearest, r = p, rain[p].copy()
            power = powers[nearest].copy()
            expected = features_for_point(power, r, row.elevation_m).loc[row.issue_date]
            np.testing.assert_allclose(
                expected.to_numpy(float), [getattr(row, c) for c in expected.index]
            )
            power.loc[power.index > pd.Timestamp(row.observation_cutoff)] = 999.0
            r.loc[r.index > pd.Timestamp(row.observation_cutoff)] = 999.0
            changed = features_for_point(power, r, row.elevation_m).loc[row.issue_date]
            np.testing.assert_allclose(expected.to_numpy(float), changed.to_numpy(float))
        report["models"][name] = {
            "status": "PASS",
            "daily_labels": len(labels),
            "training_pairs": total,
            "last_observed_target": labels.target_date.max(),
            "latest_lead_1_training_issue": spec["last_training_issue_by_lead"]["1"],
            "forecast_issue_date": manifest["issue_date"],
            "first_prediction_date": spec["first_prediction_date"],
            "last_prediction_date": spec["last_prediction_date"],
            "inference_locations": spec["inference_locations"],
            "all_60_leads_checked": True,
            "all_labels_recomputed": True,
            "future_feature_perturbation_check": True,
        }
        print(name, report["models"][name], flush=True)
    (args.root / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
