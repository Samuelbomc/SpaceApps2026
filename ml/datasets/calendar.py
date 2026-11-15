"""Known target-date calendar predictors, independent of source download tools."""

import numpy as np
import pandas as pd


def target_calendar(dates):
    dates = pd.DatetimeIndex(dates)
    return {
        "target_day_of_year_sin": np.sin(2 * np.pi * (dates.day_of_year - 1) / 365.2425),
        "target_day_of_year_cos": np.cos(2 * np.pi * (dates.day_of_year - 1) / 365.2425),
        "target_week_of_year": dates.isocalendar().week.to_numpy(dtype=float),
    }
