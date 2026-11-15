"""Validate prepared datasets and label-free forecast inputs without training."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.scripts import prepare_expanded_datasets as prep


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--dataset-root", type=Path)
    parser.add_argument("--forecast-date", default="2026-11-10")
    args = parser.parse_args()
    prep.discover_index(args.forecast_date)
    pp, powers, _ = prep.load_power()
    sp, moisture, _, _, _ = prep.load_moisture()
    rain, _ = prep.load_rain(pp + sp)
    checks_all = {}
    roots = (
        [args.dataset_root]
        if args.dataset_root
        else [Path("data/prepared/expanded")]
        + [Path(f"data/prepared/horizons/{h}d") for h in (15, 30, 60)]
    )
    for root in roots:
        manifest = json.loads((root / "manifest.json").read_text())
        policy = json.loads((root / "preparation.json").read_text())
        assert policy["power_time_standard"] == "LST"
        checks = {}
        for name, spec in manifest.items():
            frame = pd.read_csv(spec["path"])
            forecast = pd.read_csv(spec["inference_path"])
            features, horizon = spec["features"], spec["horizon_days"]
            assert len(frame) == spec["rows"] and len(forecast) == spec["inference_rows"]
            assert np.isfinite(frame[features + ["target"]].to_numpy(float)).all()
            assert np.isfinite(forecast[features].to_numpy(float)).all()
            assert not any(
                c == "target"
                or c.startswith("target_observed")
                or c.startswith("target_retrieval")
                or c.startswith("target_uncertainty")
                or c.startswith("target_recommended")
                for c in forecast
            )
            assert set(forecast.issue_date) == {args.forecast_date}
            for table in (frame, forecast):
                assert not table.duplicated(["point_id", "issue_date"]).any()
                issue, cutoff = (
                    pd.to_datetime(table.issue_date),
                    pd.to_datetime(table.observation_cutoff),
                )
                assert ((issue - cutoff).dt.days == 2).all()
                assert (
                    (issue - pd.to_datetime(table.radiation_observation_cutoff)).dt.days == 7
                ).all()
                assert ((pd.to_datetime(table.target_start) - issue).dt.days == 1).all()
                assert ((pd.to_datetime(table.target_end) - issue).dt.days == horizon).all()
                if name == "moisture":
                    assert table.smap_age_days.between(0, 14).all()
                    assert (pd.to_datetime(table.smap_latest_observation_date) <= cutoff).all()
            assert not any(c.startswith("target") for c in features)
            minimum = (
                int(np.ceil(0.8 * horizon))
                if name.startswith("temperature")
                else (horizon if name == "precipitation" else 1)
            )
            assert frame.target_observed_days.between(minimum, horizon).all()
            if name == "moisture":
                assert (
                    frame.target_recommended_retrieval_count <= frame.target_retrieval_count
                ).all()
            for row in frame.iloc[[0, len(frame) // 2, len(frame) - 1]].itertuples():
                start, end = pd.Timestamp(row.target_start), pd.Timestamp(row.target_end)
                p = int(row.point_id.rsplit("_", 1)[-1])
                if name.startswith("temperature"):
                    col = {
                        "temperature_mean": "T2M",
                        "temperature_min": "T2M_MIN",
                        "temperature_max": "T2M_MAX",
                    }[name]
                    s = powers[p][col].loc[start:end]
                    expected = s.mean()
                    assert end <= powers[p][col].last_valid_index()
                elif name == "precipitation":
                    s = rain[p].loc[start:end]
                    assert s.notna().all()
                    expected = s.sum()
                else:
                    s = moisture[p - len(pp)].loc[start:end]
                    expected = s.mean()
                    assert end <= moisture[p - len(pp)].last_valid_index()
                assert s.count() == row.target_observed_days
                assert np.isclose(expected, row.target), (name, expected, row.target)
            for row in forecast.itertuples():
                p = int(row.point_id.rsplit("_", 1)[-1])
                nearest = (
                    p
                    if name != "moisture"
                    else int(np.argmin(np.sum((np.array(pp) - sp[p - len(pp)]) ** 2, axis=1)))
                )
                pw, rr = powers[nearest].copy(), rain[p].copy()
                cutoff = pd.Timestamp(row.observation_cutoff)
                expected = prep.climate_features(pw, rr, row.elevation_m).loc[row.issue_date]
                # A future perturbation must not alter the forecast inputs.
                pw.loc[pw.index > cutoff] = 999.0
                rr.loc[rr.index > cutoff] = 999.0
                changed = prep.climate_features(pw, rr, row.elevation_m).loc[row.issue_date]
                np.testing.assert_allclose(expected.to_numpy(float), changed.to_numpy(float))
                np.testing.assert_allclose(
                    expected.to_numpy(float), [getattr(row, c) for c in expected.index]
                )
                if name == "moisture":
                    available = moisture[p - len(pp)].loc[:cutoff]
                    actual_date = available.last_valid_index()
                    assert str(actual_date.date()) == row.smap_latest_observation_date
                    assert np.isclose(available.dropna().iloc[-1], row.smap_last_valid_m3_m3)
                    week = available.loc[cutoff - pd.Timedelta(days=6) : cutoff]
                    baseline = week.mean() if week.notna().any() else available.dropna().iloc[-1]
                    assert np.isclose(baseline, row.smap_mean_7d)
            checks[name] = {
                "status": "PASS",
                "horizon_days": horizon,
                "rows": len(frame),
                "last_training_issue": frame.issue_date.max(),
                "last_target_end": frame.target_end.max(),
                "inference_rows": len(forecast),
                "inference_issue_date": args.forecast_date,
                "finite_features_and_targets": True,
                "raw_labels_recomputed": 3,
                "future_feature_perturbation_check": True,
                "models_retrained": False,
            }
            print(horizon, name, checks[name], flush=True)
        (root / "validation.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
        checks_all[str(root)] = checks
    Path("data/prepared/readiness.json").write_text(
        json.dumps(checks_all, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
