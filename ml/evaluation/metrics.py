"""Numerical regression metrics shared by forecast experiments."""

import numpy as np


def metrics(actual, prediction):
    actual, prediction = np.asarray(actual, dtype=float), np.asarray(prediction, dtype=float)
    if (
        actual.shape != prediction.shape
        or actual.size == 0
        or not np.isfinite(actual).all()
        or not np.isfinite(prediction).all()
    ):
        raise ValueError("Metrics require equally shaped finite, nonempty arrays")
    error = prediction - actual
    denominator = np.sum((actual - actual.mean()) ** 2)
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt((error**2).mean())),
        "bias": float(error.mean()),
        "r2": float(1 - (error**2).sum() / denominator) if denominator > 0 else None,
    }
