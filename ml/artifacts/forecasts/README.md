# Current daily forecast models

Five output-named models, each supporting lead_days 1-60. models.json indexes the defaults. model.json is the all-data refit; evaluation_model.json reproduces holdout scores. See ml/README.md and ml/docs/model-results.md. There are no multi-day aggregate output models in this collection.

Git includes production model.json files, runtime metadata and small score reports. Evaluation-only boosters, holdout arrays and the full current prediction export remain local. A small runnable input snapshot is in ml/examples; python -m ml.sample_forecasts --example uses it without training data.
