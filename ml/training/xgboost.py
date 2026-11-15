"""Adapter opcional. Cada target tiene un Booster y un archivo model_N.json."""

import json


class XGBoostRegressors:
    def __init__(self, boosters, features, config):
        self.boosters, self.features = boosters, features
        self.config = config

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
            version="expanded-trainer-v1-" + fingerprint(config)[:16],
            params=config["params"],
            num_boost_round=config["max_rounds"],
        )

    def fit(self, dataset, samples):
        return self._fit(dataset, samples, None)

    def fit_with_validation(self, dataset, samples, validation):
        return self._fit(dataset, samples, validation)

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
