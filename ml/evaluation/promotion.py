"""Mismo conjunto temporal para candidato, baseline y campeón; menor MAE es mejor."""

import math
from datetime import timedelta

from packages.contracts.training import PreparedDataset, TrainingPolicy


def temporal_split(dataset: PreparedDataset, cutoff, policy: TrainingPolicy):
    samples = sorted(dataset.samples, key=lambda sample: sample.feature_date)
    if any(not sample.labels_verified or sample.label_available_on > cutoff for sample in samples):
        raise ValueError("El dataset incluye etiquetas no verificadas o todavía no disponibles.")
    if not samples:
        return [], []
    validation_start = samples[-1].feature_date - timedelta(days=policy.validation_days - 1)
    validation = [sample for sample in samples if sample.feature_date >= validation_start]
    # Purga: ninguna etiqueta de entrenamiento puede tocar las entradas de validación.
    training = [sample for sample in samples if sample.label_end < validation_start]
    return training, validation


def mae(samples, predictions, targets):
    if len(samples) != len(predictions) or not samples:
        raise ValueError("Las predicciones deben cubrir exactamente las muestras de validación.")
    scores = {}
    for target in targets:
        errors = []
        for sample, prediction in zip(samples, predictions):
            if set(prediction) != set(targets) or not math.isfinite(prediction[target]):
                raise ValueError("Predicción incompleta o no finita durante la evaluación.")
            error = abs(sample.targets[target] - prediction[target])
            if not math.isfinite(error):
                raise ValueError("Error no finito durante la evaluación.")
            errors.append(error)
        scores[target] = math.fsum(error / len(errors) for error in errors)
    return scores


def promotion_decision(candidate, baseline, incumbent, policy):
    reasons = []
    if set(candidate) != set(policy.max_mae):
        return False, ["Faltan límites MAE explícitos para todos los targets."]
    for target, error in candidate.items():
        if error > policy.max_mae[target]:
            reasons.append(f"{target}: supera el error máximo permitido.")
        for label, reference in (("baseline", baseline), ("campeón", incumbent)):
            if reference is not None:
                limit = reference[target] * (1 - policy.min_relative_improvement)
                if not error < reference[target] or error > limit:
                    reasons.append(f"{target}: no mejora suficientemente al {label} en la misma validación.")
    return not reasons, reasons
