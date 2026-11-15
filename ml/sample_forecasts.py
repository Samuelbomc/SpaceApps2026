"""Show each of the next seven days by default, using prepared forecast inputs."""
import argparse
import json
from pathlib import Path

import pandas as pd

from ml.configs.forecasting import UNITS
from ml.inference.forecast import ForecastPredictor

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = REPO_ROOT/"ml/artifacts/forecasts"


def sample_for_model(horizon_days: int,model_name: str,sample_index: int,*,example=False):
    metadata=json.loads((ARTIFACT_ROOT/model_name/"training.json").read_text())
    local=REPO_ROOT/"data/prepared/daily"
    use_example=example or not (local/model_name/"inference.csv").is_file()
    inputs=REPO_ROOT/"ml/examples" if use_example else local
    manifest=json.loads((inputs/"manifest.json").read_text())
    if metadata["preparation_recipe_version"]!=manifest["recipe_version"]:
        raise ValueError("Dataset recipe differs from the trained daily model")
    path=inputs/manifest["models"][model_name]["path"] if use_example else inputs/model_name/"inference.csv"
    frame=pd.read_csv(path)
    valid=frame[frame.lead_days==horizon_days].reset_index(drop=True)
    if not 0<=sample_index<len(valid):
        raise IndexError(f"sample_index must be 0..{len(valid)-1}")
    selected=valid.iloc[[sample_index]]
    prediction=float(ForecastPredictor(model_name,horizon_days,artifact_root=ARTIFACT_ROOT).predict(selected)[0])
    row=selected.iloc[0]
    return {"horizon_days":horizon_days,"lead_days":horizon_days,"model":model_name,"point_id":row.point_id,"latitude":float(row.latitude),"longitude":float(row.longitude),"issue_date":row.issue_date,"target_date":row.target_date,"target_start":row.target_date,"target_end":row.target_date,"prediction":prediction,"units":UNITS[model_name],"forecast_type":"individual_day","input_source":"bundled example snapshot" if use_example else "local prepared observations"}


def format_table(results):
    frame=pd.DataFrame(results)
    issues=", ".join(sorted(frame.issue_date.unique()))
    lines=[f"Forecast issue date: {issues} (from prepared observations)"]
    lines.append("Inputs: "+", ".join(sorted(frame.input_source.unique())))
    for name,label in (("temperature_mean","Climate"),("moisture","Moisture")):
        row=frame[frame.model==name].iloc[0]
        lines.append(f"{label} location: {row.point_id}, latitude {row.latitude:.5f}, longitude {row.longitude:.5f}")
    lines.append("Moisture uses its native SMAP cell; its location differs from the climate point.")
    table=frame.pivot(index="target_date",columns="model",values="prediction")
    table=table[list(UNITS)].rename(columns={"temperature_mean":"Mean C","temperature_min":"Min C","temperature_max":"Max C","precipitation":"Rain mm/day","moisture":"Moisture m3/m3"})
    table.index.name="Date"
    table.columns.name=None
    lines.extend(["",table.to_string(formatters={c:(lambda x:f"{x:.4f}") if c=="Moisture m3/m3" else (lambda x:f"{x:.2f}") for c in table.columns}),"","Predictions are individual-day estimates, not observed values or calibrated uncertainty bounds."])
    return "\n".join(lines)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument("--sample-index",type=int,default=0)
    period=parser.add_mutually_exclusive_group()
    period.add_argument("--days",type=int,help="number of consecutive future days (default: 7; maximum: 60)")
    period.add_argument("--leads",type=int,nargs="+",help="specific future days, e.g. 1 7 15 30 60")
    parser.add_argument("--format",choices=["table","json"],default="table")
    parser.add_argument("--example",action="store_true",help="use the small bundled snapshot, even when local data exist")
    args=parser.parse_args()
    days=args.days if args.days is not None else 7
    if days not in range(1,61):
        parser.error("days must be 1..60")
    leads=sorted(set(args.leads)) if args.leads is not None else list(range(1,days+1))
    if any(h not in range(1,61) for h in leads):
        parser.error("leads must be 1..60")
    results=[sample_for_model(lead,name,args.sample_index,example=args.example) for lead in leads for name in UNITS]
    print(json.dumps(results,indent=2) if args.format=="json" else format_table(results))


if __name__=="__main__":
    main()
