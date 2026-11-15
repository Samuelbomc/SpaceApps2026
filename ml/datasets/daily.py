"""Read normalized direct-daily training examples in bounded batches."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.datasets.calendar import target_calendar


def materialize(features,labels,feature_ids,label_ids,lead):
    """Join one batch; all future-valued columns are labels or calendar dates."""
    batch = features.iloc[feature_ids].reset_index(drop=True).copy()
    selected = labels.iloc[label_ids].reset_index(drop=True)
    if not np.array_equal(batch.point_id,selected.point_id):
        raise ValueError("Pair index links different locations")
    target_dates = pd.to_datetime(selected.target_date)
    if not ((target_dates-pd.to_datetime(batch.issue_date)).dt.days==lead).all():
        raise ValueError("Pair index has incorrect lead")
    for column in selected:
        if column!="point_id":
            batch[column] = selected[column].to_numpy()
    batch["lead_days"] = lead
    for name,values in target_calendar(target_dates).items():
        batch[name] = values
    # A daily target occupies a single date, not a multi-day aggregate window.
    batch["target_start"] = batch.target_date
    batch["target_end"] = batch.target_date
    return batch


def iter_training_batches(model_name,*,leads=range(1,61),batch_size=65536,root=Path("data/prepared/daily")):
    if batch_size<1:
        raise ValueError("batch_size must be positive")
    root = Path(root)
    spec = json.loads((root/"manifest.json").read_text())["models"][model_name]
    folder = root/model_name
    features = pd.read_csv(folder/"features.csv")
    labels = pd.read_csv(folder/"labels.csv")
    for lead in leads:
        if lead not in range(1,61):
            raise ValueError("lead must be 1..60")
        with np.load(folder/"pairs"/f"lead_{lead:02d}.npz") as pairs:
            for start in range(0,len(pairs["feature_id"]),batch_size):
                rows = slice(start,start+batch_size)
                batch = materialize(features,labels,pairs["feature_id"][rows],pairs["label_id"][rows],lead)
                if not np.isfinite(batch[spec["features"]+["target"]].to_numpy(float)).all():
                    raise ValueError("Nonfinite training values")
                yield batch
