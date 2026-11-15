"""Validate the available-data model tables and write their manifest."""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    root = Path("data/prepared/available")
    summary = {}
    for group, models in {"temperature": {"temperature_mean":"target_mean_c", "temperature_min":"target_min_c", "temperature_max":"target_max_c"}, "water":{"precipitation":"target", "moisture":"target"}}.items():
        report = json.loads((root/group/"validation_report.json").read_text())
        for model,target in models.items():
            features = report["required_features"] if group == "temperature" else report["required_features"][model]
            path = root/group/f"{model}.csv"
            frame = pd.read_csv(path)
            assert len(frame) > 0, f"{model} has no complete examples"
            assert np.isfinite(frame[features+[target]].to_numpy(float)).all(), model
            assert not frame.duplicated(["point_id","issue_date"]).any(), model
            issue = pd.to_datetime(frame.issue_date)
            cutoff = pd.to_datetime(frame.observation_cutoff)
            assert ((issue-cutoff).dt.days == 2).all(), model
            assert ((pd.to_datetime(frame.target_start)-issue).dt.days == 1).all(), model
            assert ((pd.to_datetime(frame.target_end)-issue).dt.days == 7).all(), model
            measured = pd.to_datetime(frame.smap_latest_observation_date)
            assert measured.notna().all() and (measured <= cutoff).all(), model
            assert ((cutoff-measured).dt.days <= 6).all(), model
            summary[model] = {"path":str(path), "rows":len(frame), "features":features, "target":target,
                              "first_issue":str(issue.min().date()), "last_issue":str(issue.max().date()),
                              "locations":int(frame.point_id.nunique()), "distinct_issue_dates":int(issue.nunique()),
                              "validation":"PASS: finite inputs/targets, unique keys, correct date windows, recent antecedent SMAP"}
    (root/"manifest.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
