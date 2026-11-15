"""Ciclo diario compacto: seleccionar sin test, evaluar y publicar con evidencia."""

import gc
import json
import math
import uuid
from datetime import UTC, datetime
from statistics import median

from ml.evaluation.promotion import promotion_decision
from ml.training.daily_data import DailyDesign, DailyTrainingSources
from packages.contracts.training import ModelRelease, TrainingOutcome, TrainingPolicy
from pipelines.training.snapshots import fingerprint


class DailyFittedModel:
    def __init__(self, booster, config):
        self.booster, self.config = booster, config

    def save(self, directory):
        self.booster.save_model(directory / "model.json")
        (directory / "training.json").write_text(json.dumps(self.config, sort_keys=True))


def quantile_matrix(design, partition, params, *, fold=None, ref=None):
    import xgboost as xgb

    class Batches(xgb.DataIter):
        def __init__(self):
            super().__init__(release_data=True)
            self.reset()

        def reset(self):
            self.iterator = iter(design.batches(partition, fold))
            self.current = None

        def next(self, input_data):
            batch = next(self.iterator, None)
            if batch is None:
                return False
            matrix, target, baseline, *_ = batch
            response = (
                target - baseline
                if design.spec["prediction_mode"] == "baseline_plus_change"
                else target
            )
            self.current = matrix, response
            input_data(data=matrix, label=response, feature_names=design.spec["features"])
            return True

    return xgb.QuantileDMatrix(
        Batches(), nthread=params["nthread"], max_bin=params["max_bin"], ref=ref
    )


def score(design, booster, partition, fold=None):
    total, error, baseline_error = 0, 0.0, 0.0
    for matrix, target, baseline, *_ in design.batches(partition, fold):
        prediction = booster.inplace_predict(matrix)
        if design.spec["prediction_mode"] == "baseline_plus_change":
            prediction = prediction + baseline
        if not design.np.isfinite(prediction).all():
            raise ValueError("El modelo diario produjo valores no finitos.")
        error += float(design.np.abs(prediction.astype(float) - target.astype(float)).sum())
        baseline_error += float(design.np.abs(baseline.astype(float) - target.astype(float)).sum())
        total += len(target)
    if not total:
        raise ValueError("La partición diaria no tiene etiquetas.")
    return {"mae": error / total, "baseline_mae": baseline_error / total, "rows": total}


class DailyModelTrainingPipeline:
    def __init__(self, config, source_root, snapshot_root, artifacts, registry):
        self.config, self.artifacts, self.registry = config, artifacts, registry
        self.snapshots = DailyTrainingSources(config, source_root, snapshot_root)

    def run(self, region, cutoff):
        snapshot = self.snapshots.capture(region, cutoff)
        outcomes = []
        for name in self.config["models"]:
            slot = f"{region['region_id']}:daily:{name}"
            if (
                snapshot is None
                or name
                not in json.loads((snapshot.root / "source-manifest.json").read_text())["manifest"][
                    "models"
                ]
            ):
                outcome = TrainingOutcome(
                    slot=slot,
                    status="insufficient_labels",
                    message="Faltan features, etiquetas diarias e índices validados de la receta daily-direct-1-60-v1.",
                )
            else:
                outcome = self._train(region, slot, name, snapshot)
            outcomes.append(outcome)
            gc.collect()
        self.registry.record_outcomes([outcome.model_dump(mode="json") for outcome in outcomes])
        return outcomes

    def _train(self, region, slot, name, snapshot):
        import xgboost as xgb

        config = self.config
        spec = config["models"][name]
        design = DailyDesign(snapshot, name, spec, label_lag_days=config["label_lag_days"])
        base = {"slot": slot, "dataset_id": snapshot.dataset_id}
        if design.boundaries is None:
            return TrainingOutcome(
                **base,
                status="insufficient_labels",
                message="Faltan fechas para las cuatro ventanas diarias purgadas y su test.",
            )
        counts = {"development": design.summary("development"), "test": design.summary("test")}
        folds = [
            (design.summary("train", fold), design.summary("validation", fold)) for fold in range(4)
        ]
        if (
            counts["test"]["rows"] < config["min_test_samples"]
            or counts["test"]["locations"] < config["min_spatial_locations"]
            or any(
                train["rows"] < config["min_train_samples"]
                or valid["rows"] < config["min_validation_samples"]
                or min(train["locations"], valid["locations"]) < config["min_spatial_locations"]
                for train, valid in folds
            )
        ):
            return TrainingOutcome(
                **base,
                status="insufficient_labels",
                message="Faltan pares o celdas independientes por fold/test después de la purga.",
            )
        identity = fingerprint(
            {"design": design.identity, "configuration": config, "region": region}
        )
        incumbent = self.registry.current(slot)
        if incumbent is not None:
            self.artifacts.verify(incumbent)
        if self.registry.attempt(identity) is not None:
            return TrainingOutcome(
                **base,
                status="unchanged",
                version=incumbent.version if incumbent else None,
                message="Estas entradas efectivas, evidencia y configuración ya fueron evaluadas.",
            )
        if incumbent is not None:
            since = int(
                design.np.datetime64(
                    incumbent.evaluated_through or incumbent.trained_through, "D"
                ).astype(design.np.int32)
            )
            fresh = set()
            for _, li, _ in design.pairs:
                fresh.update(design.target_date[li][design.target_date[li] > since].tolist())
            if len(fresh) < config["min_new_labels"]:
                return TrainingOutcome(
                    **base,
                    status="insufficient_labels",
                    version=incumbent.version,
                    message="Aún faltan nuevas fechas observadas; los pares de varios leads no cuentan como etiquetas independientes.",
                )
        candidates = [
            {"candidate": i, "parameters": {**config["params"], **choice}, "folds": []}
            for i, choice in enumerate(config["candidates"])
        ]
        for fold, (train_summary, valid_summary) in enumerate(folds):
            training = quantile_matrix(design, "train", config["params"], fold=fold)
            validation = quantile_matrix(
                design, "validation", config["params"], fold=fold, ref=training
            )
            for candidate in candidates:
                model = xgb.train(
                    candidate["parameters"],
                    training,
                    num_boost_round=config["max_rounds"],
                    evals=[(validation, "validation")],
                    early_stopping_rounds=config["early_stopping_rounds"],
                    verbose_eval=False,
                )
                rounds = model.best_iteration + 1
                measured = score(design, model[:rounds], "validation", fold)
                candidate["folds"].append(
                    {
                        "fold": fold + 1,
                        "rounds": rounds,
                        **measured,
                        "train": train_summary,
                        "validation": valid_summary,
                    }
                )
                del model
            del training, validation
            gc.collect()
        for candidate in candidates:
            total = sum(fold["rows"] for fold in candidate["folds"])
            candidate["cv_mae"] = (
                math.fsum(fold["mae"] * fold["rows"] for fold in candidate["folds"]) / total
            )
            candidate["cv_baseline_mae"] = (
                math.fsum(fold["baseline_mae"] * fold["rows"] for fold in candidate["folds"])
                / total
            )
            candidate["selected_rounds"] = int(
                median([fold["rounds"] for fold in candidate["folds"]])
            )
        best = min(candidates, key=lambda candidate: candidate["cv_mae"])
        development = quantile_matrix(design, "development", best["parameters"])
        model = xgb.train(best["parameters"], development, num_boost_round=best["selected_rounds"])
        del development
        gc.collect()
        test = score(design, model, "test")
        policy = TrainingPolicy(
            version="daily-policy-" + fingerprint(config)[:16],
            split_strategy="rolling_origin",
            max_mae={name: spec["reference_baseline_mae"]},
            min_relative_improvement=config["min_relative_improvement"],
            publication_allowed=config["publication_allowed"],
        )
        accepted, reasons = promotion_decision(
            {name: best["cv_mae"]}, {name: best["cv_baseline_mae"]}, None, policy
        )
        champion_metrics = None
        comparable = True
        if incumbent is not None:
            comparable = incumbent.trained_through < self._date(counts["test"]["first_issue"] - 2)
            if comparable:
                if (
                    incumbent.recipe_version != config["recipe_version"]
                    or incumbent.feature_names != spec["features"]
                    or incumbent.target_units != {name: spec["unit"]}
                ):
                    raise ValueError(
                        "El campeón diario requiere una migración explícita de esquema."
                    )
                champion = xgb.Booster(params={"nthread": 1})
                champion.load_model(self.artifacts.verify(incumbent) / "model.json")
                champion_metrics = {name: score(design, champion, "test")["mae"]}
        test_accepted, test_reasons = promotion_decision(
            {name: test["mae"]}, {name: test["baseline_mae"]}, champion_metrics, policy
        )
        accepted &= test_accepted
        reasons += ["test: " + reason for reason in test_reasons]
        publication_ready = (
            config["publication_allowed"] and snapshot.publication_ready and comparable
        )
        if accepted and not publication_ready:
            reasons.append(
                "Evaluación técnica apta; falta revisión científica, disponibilidad o una ventana posterior al campeón."
            )
        metrics = {
            "validation_method": "daily_rolling_origin",
            "candidate_mae": {name: best["cv_mae"]},
            "baseline_mae": {name: best["cv_baseline_mae"]},
            "test": {
                "candidate_mae": {name: test["mae"]},
                "baseline_mae": {name: test["baseline_mae"]},
                "incumbent_mae": champion_metrics,
                "samples": test["rows"],
            },
            "candidates": candidates,
            "counts": counts,
            "publication_ready": publication_ready,
            "reasons": reasons,
        }
        version = uuid.uuid4().hex
        model_config = {
            "model_name": name,
            "training_pipeline": "rolling_origin",
            "forecast_type": "direct_daily",
            "preparation_recipe_version": config["recipe_version"],
            "supported_leads": list(range(1, 61)),
            "features": spec["features"],
            "prediction_mode": spec["prediction_mode"],
            "baseline_feature": spec["baseline_feature"],
            "units": spec["unit"],
            "selected_candidate": best["candidate"],
            "selected_rounds": best["selected_rounds"],
            "parameters": best["parameters"],
            "candidates": candidates,
            "test_metrics": {
                "model": {"mae": test["mae"]},
                "persistence": {"mae": test["baseline_mae"]},
            },
            "source_snapshot": snapshot.dataset_id,
            "artifact_note": "Frozen pre-test fit; no refit on test labels.",
        }
        fitted = DailyFittedModel(model, model_config)
        metadata = {
            "slot": slot,
            "version": version,
            "snapshot_sha256": snapshot.sha256,
            "training_fingerprint": identity,
            "metrics": metrics,
            "daily_model": name,
        }
        hashes = self.artifacts.save(version, fitted, metadata)
        observed = max(int(design.target_date[li].max()) for _, li, _ in design.pairs if len(li))
        release = ModelRelease(
            slot=slot,
            version=version,
            model_kind="soil" if name == "moisture" else "climate",
            region_id=region["region_id"],
            horizon_days=60,
            dataset_id=snapshot.dataset_id,
            training_fingerprint=identity,
            recipe_version=config["recipe_version"],
            policy_version=policy.version,
            trained_through=self._date(counts["development"]["last_target"]),
            evaluated_through=self._date(observed),
            feature_names=spec["features"],
            target_units={name: spec["unit"]},
            artifact_sha256=hashes,
            metrics=metrics,
            created_at=datetime.now(UTC),
            validation_status="validated" if accepted and publication_ready else "experimental",
            spatial_scope=config["spatial_scope"],
            forecast_type="direct_daily",
            supported_leads=list(range(1, 61)),
        )
        status = (
            "published"
            if accepted and publication_ready
            else "pending_review"
            if accepted
            else "rejected"
        )
        if status == "published" and not self.registry.publish(
            release, incumbent.version if incumbent else None
        ):
            status = "unchanged"
            reasons.append("Otro proceso publicó primero; se conserva el registro vigente.")
        message = "; ".join(reasons) or "Modelo diario validado y publicado."
        self.registry.record_attempt(
            identity,
            {
                "status": status,
                "release": release.model_dump(mode="json"),
                "metrics": metrics,
                "message": message,
            },
        )
        return TrainingOutcome(**base, status=status, version=version, message=message)

    @staticmethod
    def _date(day):
        from datetime import date, timedelta

        return date(1970, 1, 1) + timedelta(days=int(day))
