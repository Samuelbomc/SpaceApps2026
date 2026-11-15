"""Plan temporal por objetivo, equivalente a los experimentos canónicos."""

from dataclasses import dataclass
from datetime import timedelta

from packages.contracts.training import LabeledSample, PreparedDataset


@dataclass(frozen=True)
class RollingOriginPlan:
    development: list[LabeledSample]
    validation: list[LabeledSample]
    test: list[LabeledSample]
    folds: dict[str, list[tuple[list[LabeledSample], list[LabeledSample]]]]


def _combine(rows):
    combined = {}
    for row in rows:
        key = (row.feature_date, row.spatial_id)
        if key not in combined:
            combined[key] = row.model_copy(
                update={
                    "targets": dict(row.targets),
                    "baseline": dict(row.baseline),
                    "label_observed_days": dict(row.label_observed_days),
                }
            )
        else:
            combined[key].targets.update(row.targets)
            combined[key].baseline.update(row.baseline)
            combined[key].label_observed_days.update(row.label_observed_days)
    return [combined[key] for key in sorted(combined)]


def rolling_origin_plan(dataset: PreparedDataset, cutoff):
    """80 % inicial, cuatro ventanas 40/55/70/85 %, test 20 % y purga t-2.

    Se agrupan todas las celdas de una fecha. Cada objetivo usa sus propias
    fechas disponibles; una etiqueta ausente de lluvia no altera la de temperatura.
    """
    if any(not row.labels_verified or row.label_available_on > cutoff for row in dataset.samples):
        raise ValueError("El dataset incluye etiquetas no verificadas o todavía no disponibles.")
    development, validation_rows, testing, folds = [], [], [], {}
    for target in dataset.target_units:
        rows = sorted(
            [
                row.model_copy(
                    update={
                        "targets": {target: row.targets[target]},
                        "baseline": {target: row.baseline[target]},
                        "label_observed_days": {target: row.label_observed_days[target]}
                        if target in row.label_observed_days
                        else {},
                    }
                )
                for row in dataset.samples
                if target in row.targets
            ],
            key=lambda row: (row.feature_date, row.spatial_id),
        )
        dates = sorted({row.feature_date for row in rows})
        folds[target] = []
        if len(dates) < 5:
            continue
        test_start = dates[int(len(dates) * 0.8)]
        test = [row for row in rows if row.feature_date >= test_start]
        test_cutoff = min(
            row.observation_cutoff or row.feature_date - timedelta(days=2) for row in test
        )
        dev = [row for row in rows if row.feature_date < test_start and row.label_end < test_cutoff]
        dev_dates = sorted({row.feature_date for row in dev})
        if len(dev_dates) < 5:
            continue
        boundaries = [
            dev_dates[int(len(dev_dates) * fraction)] for fraction in (0.4, 0.55, 0.7, 0.85)
        ]
        boundaries.append(test_start)
        for start, end in zip(boundaries, boundaries[1:]):
            train = [
                row
                for row in dev
                if row.feature_date < start and row.label_end < start - timedelta(days=2)
            ]
            valid = [
                row
                for row in dev
                if start <= row.feature_date < end and row.label_end < end - timedelta(days=2)
            ]
            folds[target].append((train, valid))
            validation_rows.extend(valid)
        development.extend(dev)
        testing.extend(test)
    return RollingOriginPlan(
        _combine(development), _combine(validation_rows), _combine(testing), folds
    )
