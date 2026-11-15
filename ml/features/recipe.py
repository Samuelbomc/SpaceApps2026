"""Receta causal compartida por entrenamiento e ingesta puntual, sin estado global."""

import numpy as np
import pandas as pd


def climate_features(power, rain, elevation):
    index = power.index
    f = pd.DataFrame(index=index)
    # Feature-only causal filling: no backfill, future interpolation or label filling.
    raw_power, raw_rain = power, rain
    power, rain = power.ffill(limit=7), rain.ffill(limit=3)
    for col in ("T2M", "T2M_MIN", "T2M_MAX", "RH2M", "QV2M", "WS2M"):
        for days in (7, 14, 30):
            f[f"{col.lower()}_mean_{days}d"] = (
                power[col].rolling(days, min_periods=days).mean().shift(2)
            )
    f["t2m_last"] = power.T2M.shift(2)
    # Radiation is published later than meteorology. Use a seven-day lag
    # consistently in training and inference rather than assume a two-day feed.
    f["radiation_sum_7d"] = power.ALLSKY_SFC_SW_DWN.rolling(7, min_periods=7).sum().shift(7)
    for days in (1, 3, 7, 14, 30):
        f[f"gpm_late_sum_{days}d_mm"] = rain.rolling(days, min_periods=days).sum().shift(2)
    f["gpm_late_max_daily_7d_mm"] = rain.rolling(7, min_periods=7).max().shift(2)
    f["rainy_days_7d"] = (rain > 0).where(rain.notna()).rolling(7, min_periods=7).sum().shift(2)
    f["elevation_m"] = elevation
    f["week_of_year"] = index.isocalendar().week.to_numpy(dtype=float)
    f["day_of_year_sin"] = np.sin(2 * np.pi * (index.day_of_year - 1) / 365.2425)
    f["day_of_year_cos"] = np.cos(2 * np.pi * (index.day_of_year - 1) / 365.2425)
    f.attrs["audit"] = {
        "input_power_filled_values_30d": (raw_power.isna() & power.notna())
        .sum(axis=1)
        .rolling(30, min_periods=1)
        .sum()
        .shift(2),
        "input_rain_filled_days_30d": (raw_rain.isna() & rain.notna())
        .rolling(30, min_periods=1)
        .sum()
        .shift(2),
        "radiation_observation_cutoff": pd.Series(
            index - pd.Timedelta(days=7), index=index
        ).dt.strftime("%Y-%m-%d"),
    }
    return f


def features_for_point(power, rain, elevation):
    index = power.index
    f = climate_features(power, rain, elevation)
    audit = f.attrs.pop("audit")
    for col in power:
        lag = 7 if col == "ALLSKY_SFC_SW_DWN" else 2
        f[col.lower() + "_last_daily"] = power[col].ffill(limit=7).shift(lag)
        dates = pd.Series(pd.NaT, index=index, dtype="datetime64[ns]")
        dates.loc[power[col].notna()] = power.index[power[col].notna()]
        latest = dates.ffill(limit=7).shift(lag)
        f[col.lower() + "_age_days"] = (
            (pd.Series(index, index=index) - pd.Timedelta(days=lag)) - latest
        ).dt.days
    dates = pd.Series(pd.NaT, index=index, dtype="datetime64[ns]")
    dates.loc[rain.notna()] = rain.index[rain.notna()]
    f["gpm_age_days"] = (
        (pd.Series(index, index=index) - pd.Timedelta(days=2)) - dates.ffill(limit=3).shift(2)
    ).dt.days
    for name in ("input_power_filled_values_30d", "input_rain_filled_days_30d"):
        f[name] = audit[name]
    return f


def soil_features(climate, moisture, counts, recommended, terrain):
    """AM/PM aceptados y sus contadores; misma receta de las etiquetas diarias."""
    f = climate.copy()
    s = moisture.reindex(f.index)
    f["smap_mean_7d"] = (
        s.rolling(7, min_periods=1).mean().shift(2).fillna(s.ffill(limit=14).shift(2))
    )
    f["smap_last_valid_m3_m3"] = s.ffill(limit=14).shift(2)
    dates = pd.Series(pd.NaT, index=f.index, dtype="datetime64[ns]")
    dates.loc[s.notna()] = s.index[s.notna()]
    f["smap_age_days"] = (
        (pd.Series(f.index, index=f.index) - pd.Timedelta(days=2)) - dates.ffill(limit=14).shift(2)
    ).dt.days
    f["smap_observed_days_7d"] = s.rolling(7, min_periods=1).count().shift(2)
    f["smap_nonrecommended_retrievals_7d"] = (
        (counts - recommended).reindex(f.index).rolling(7, min_periods=1).sum().shift(2)
    )
    for key, value in terrain.items():
        f[key] = value
    return f
