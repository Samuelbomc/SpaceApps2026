"""Adapter opcional. Cada target tiene un Booster y un archivo model_N.json."""

import json


class XGBoostRegressors:
    def __init__(self, boosters, features, config):
        self.boosters, self.features = boosters, features
        self.config = config

    def predict(self, samples):
        import xgboost as xgb
        matrix = xgb.DMatrix([[sample.features[name] for name in self.features] for sample in samples], feature_names=self.features)
        predictions = {target: booster.predict(matrix).tolist() for target, booster in self.boosters.items()}
        return [{target: values[index] for target, values in predictions.items()} for index in range(len(samples))]

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
        effective_params = {"objective": "reg:squarederror", "seed": 42, "nthread": 1, **self.params}
        for target in sorted(dataset.target_units):
            matrix = xgb.DMatrix([[sample.features[name] for name in dataset.feature_names] for sample in samples],
                                 label=[sample.targets[target] for sample in samples], feature_names=dataset.feature_names)
            boosters[target] = xgb.train(effective_params,
                                         matrix, num_boost_round=self.num_boost_round)
        return XGBoostRegressors(boosters, dataset.feature_names, {"trainer_version": self.version,
                                 "xgboost_version": xgb.__version__, "params": effective_params,
                                 "num_boost_round": self.num_boost_round})

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
        return XGBoostRegressors(boosters, release.feature_names, json.loads((directory / "training.json").read_text()))
