"""Adapter opcional. Cada target tiene un Booster y un archivo model_N.json."""

import json
import math
from statistics import median


class XGBoostRegressors:
    def __init__(self, boosters, features, config, cv_predictions=None):
        self.boosters, self.features = boosters, features
        self.config = config
        self.cv_predictions = cv_predictions

    def validation_predictions(self, samples):
        if self.cv_predictions is None:
            raise ValueError("El ajuste no conserva predicciones fuera de muestra de sus folds.")
        return [
            self.cv_predictions[(row.feature_date.isoformat(), row.spatial_id)] for row in samples
        ]

    def predict(self, samples):
        import xgboost as xgb

        matrix = xgb.DMatrix(
            [[sample.features[name] for name in self.features] for sample in samples],
            feature_names=self.features,
        )
        predictions = {
            target: booster.predict(matrix).tolist() for target, booster in self.boosters.items()
        }
        for target, baseline_feature in self.config.get("residual_targets", {}).items():
            predictions[target] = [
                value + sample.features[baseline_feature]
                for value, sample in zip(predictions[target], samples)
            ]
        return [
            {target: values[index] for target, values in predictions.items()}
            for index in range(len(samples))
        ]

    def save(self, directory):
        index = {}
        for position, (target, booster) in enumerate(sorted(self.boosters.items())):
            filename = f"model_{position}.json"
            booster.save_model(directory / filename)
            index[target] = filename
        (directory / "targets.json").write_text(json.dumps(index, sort_keys=True))
        (directory / "training.json").write_text(json.dumps(self.config, sort_keys=True))
        if self.cv_predictions is not None:
            (directory / "cv_predictions.json").write_text(
                json.dumps(
                    [
                        {"feature_date": day, "spatial_id": point, "predictions": prediction}
                        for (day, point), prediction in sorted(self.cv_predictions.items())
                    ],
                    sort_keys=True,
                )
            )


class XGBoostTrainer:
    def __init__(self, *, version, params, num_boost_round):
        # Versionar explícitamente el experimento y sus hiperparámetros.
        if not version or num_boost_round < 1:
            raise ValueError("El trainer requiere versión y número de iteraciones válidos.")
        self.version, self.params, self.num_boost_round = version, dict(params), num_boost_round

    def fit(self, dataset, samples):
        import xgboost as xgb

        boosters = {}
        effective_params = {
            "objective": "reg:squarederror",
            "seed": 42,
            "nthread": 1,
            **self.params,
        }
        for target in sorted(dataset.target_units):
            matrix = xgb.DMatrix(
                [[sample.features[name] for name in dataset.feature_names] for sample in samples],
                label=[sample.targets[target] for sample in samples],
                feature_names=dataset.feature_names,
            )
            boosters[target] = xgb.train(
                effective_params, matrix, num_boost_round=self.num_boost_round
            )
        return XGBoostRegressors(
            boosters,
            dataset.feature_names,
            {
                "trainer_version": self.version,
                "xgboost_version": xgb.__version__,
                "params": effective_params,
                "num_boost_round": self.num_boost_round,
            },
        )

    def load(self, release, directory):
        import xgboost as xgb

        index = json.loads((directory / "targets.json").read_text())
        if set(index) != set(release.target_units):
            raise ValueError("Los targets guardados no coinciden con el manifiesto.")
        boosters = {}
        for target, filename in index.items():
            if filename not in release.artifact_sha256:
                raise ValueError("Modelo sin hash en el manifiesto.")
            boosters[target] = xgb.Booster()
            boosters[target].load_model(directory / filename)
        return XGBoostRegressors(
            boosters, release.feature_names, json.loads((directory / "training.json").read_text())
        )


class ExpandedXGBoostTrainer(XGBoostTrainer):
    """Cuatro regresores absolutos de clima y uno residual de humedad por horizonte."""

    def __init__(self, config):
        from pipelines.training.snapshots import fingerprint

        self.definition = config
        super().__init__(
            version="expanded-trainer-rolling-origin-v2-" + fingerprint(config)[:16],
            params=config["params"],
            num_boost_round=config["max_rounds"],
        )

    def fit(self, dataset, samples):
        return self._fit(dataset, samples, None)

    def fit_with_validation(self, dataset, samples, validation):
        return self._fit(dataset, samples, validation)

    def fit_rolling_origin(self, dataset, plan):
        import numpy as np
        import xgboost as xgb

        boosters, rounds_by_target, residuals, reports, oof, parameters = {}, {}, {}, {}, {}, {}
        specs = self.definition["sources"][str(dataset.horizon_days)]
        for target in sorted(dataset.target_units):
            spec = specs[target]
            residual = spec["prediction_mode"] == "baseline_plus_change"

            def matrix(rows):
                return xgb.DMatrix(
                    np.array(
                        [[row.features[name] for name in dataset.feature_names] for row in rows]
                    ),
                    label=[
                        row.targets[target]
                        - (row.features[spec["baseline_feature"]] if residual else 0)
                        for row in rows
                    ],
                    feature_names=dataset.feature_names,
                )

            def predict(model, rows):
                values = model.predict(matrix(rows)).tolist()
                return [
                    value + (row.features[spec["baseline_feature"]] if residual else 0)
                    for value, row in zip(values, rows)
                ]

            candidates = []
            for number, choice in enumerate(self.definition["candidates"]):
                params = {**self.params, **choice}
                errors, baseline_errors, folds, predictions = [], [], [], {}
                for fold, (train, valid) in enumerate(plan.folds[target], 1):
                    model = xgb.train(
                        params,
                        matrix(train),
                        num_boost_round=self.num_boost_round,
                        evals=[(matrix(valid), "validation")],
                        early_stopping_rounds=self.definition["early_stopping_rounds"],
                        verbose_eval=False,
                    )
                    rounds = model.best_iteration + 1
                    values = predict(model[:rounds], valid)
                    fold_errors = [
                        abs(row.targets[target] - value) for row, value in zip(valid, values)
                    ]
                    errors.extend(fold_errors)
                    baseline_errors.extend(
                        abs(row.targets[target] - row.baseline[target]) for row in valid
                    )
                    predictions.update(
                        {
                            (row.feature_date.isoformat(), row.spatial_id): value
                            for row, value in zip(valid, values)
                        }
                    )
                    folds.append(
                        {
                            "fold": fold,
                            "train_rows": len(train),
                            "validation_rows": len(valid),
                            "train_last_label": max(row.label_end for row in train).isoformat(),
                            "validation_first_cutoff": min(
                                row.observation_cutoff for row in valid
                            ).isoformat(),
                            "validation_last_label": max(
                                row.label_end for row in valid
                            ).isoformat(),
                            "rounds": rounds,
                            "mae": math.fsum(fold_errors) / len(fold_errors),
                        }
                    )
                candidates.append(
                    {
                        "candidate": number,
                        "parameters": params,
                        "cv_mae": math.fsum(errors) / len(errors),
                        "cv_baseline_mae": math.fsum(baseline_errors) / len(baseline_errors),
                        "selected_rounds": int(median([fold["rounds"] for fold in folds])),
                        "folds": folds,
                        "predictions": predictions,
                    }
                )
            best = min(candidates, key=lambda candidate: candidate["cv_mae"])
            dev = [row for row in plan.development if target in row.targets]
            boosters[target] = xgb.train(
                best["parameters"], matrix(dev), num_boost_round=best["selected_rounds"]
            )
            rounds_by_target[target], parameters[target] = (
                best["selected_rounds"],
                best["parameters"],
            )
            if residual:
                residuals[target] = spec["baseline_feature"]
            for key, value in best["predictions"].items():
                oof.setdefault(key, {})[target] = value
            reports[target] = {
                "selected_candidate": best["candidate"],
                "candidates": [
                    {key: value for key, value in candidate.items() if key != "predictions"}
                    for candidate in candidates
                ],
                "development_rows": len(dev),
            }
        return XGBoostRegressors(
            boosters,
            dataset.feature_names,
            {
                "trainer_version": self.version,
                "xgboost_version": xgb.__version__,
                "params": self.params,
                "selected_parameters": parameters,
                "selected_rounds": rounds_by_target,
                "residual_targets": residuals,
                "feature_names": dataset.feature_names,
                "target_units": dataset.target_units,
                "recipe_version": dataset.recipe_version,
                "model_kind": dataset.model_kind,
                "horizon_days": dataset.horizon_days,
                "cross_validation": reports,
                "artifact_semantics": "rolling_origin_selection; frozen_pre_test_fit; no refit on test labels",
            },
            oof,
        )

    def _fit(self, dataset, samples, validation):
        import numpy as np
        import xgboost as xgb

        boosters, rounds, residuals = {}, {}, {}
        specs = self.definition["sources"][str(dataset.horizon_days)]
        for target in sorted(dataset.target_units):
            spec = specs[target]
            residual = spec["prediction_mode"] == "baseline_plus_change"

            def matrix(rows):
                rows = [s for s in rows if target in s.targets]
                if not rows:
                    raise ValueError(f"Faltan etiquetas de {target}.")
                labels = [
                    s.targets[target] - (s.features[spec["baseline_feature"]] if residual else 0)
                    for s in rows
                ]
                return xgb.DMatrix(
                    np.array([[s.features[k] for k in dataset.feature_names] for s in rows]),
                    label=labels,
                    feature_names=dataset.feature_names,
                )

            train = matrix(samples)
            if validation is not None:
                model = xgb.train(
                    self.params,
                    train,
                    num_boost_round=self.num_boost_round,
                    evals=[(matrix(validation), "validation")],
                    early_stopping_rounds=self.definition["early_stopping_rounds"],
                    verbose_eval=False,
                )
                selected = model.best_iteration + 1
                model = model[:selected]
            else:
                selected = spec["original_selected_rounds"]
                model = xgb.train(self.params, train, num_boost_round=selected)
            boosters[target], rounds[target] = model, selected
            if residual:
                residuals[target] = spec["baseline_feature"]
        return XGBoostRegressors(
            boosters,
            dataset.feature_names,
            {
                "trainer_version": self.version,
                "xgboost_version": xgb.__version__,
                "params": self.params,
                "selected_rounds": rounds,
                "residual_targets": residuals,
                "feature_names": dataset.feature_names,
                "target_units": dataset.target_units,
                "recipe_version": dataset.recipe_version,
                "model_kind": dataset.model_kind,
                "horizon_days": dataset.horizon_days,
                "artifact_semantics": "frozen_evaluated_model; no refit on validation or test labels",
            },
        )

    def load(self, release, directory):
        loaded = super().load(release, directory)
        config = loaded.config
        if (
            config["feature_names"] != release.feature_names
            or config["target_units"] != release.target_units
            or config["recipe_version"] != release.recipe_version
            or config["horizon_days"] != release.horizon_days
            or config["model_kind"] != release.model_kind
            or any(b.feature_names != release.feature_names for b in loaded.boosters.values())
        ):
            raise ValueError("El artefacto no corresponde al esquema de la versión registrada.")
        expected = {"moisture": "smap_mean_7d"} if release.model_kind == "soil" else {}
        if config["residual_targets"] != expected:
            raise ValueError("La reconstrucción residual no coincide con el modelo registrado.")
        return loaded
