"""Public anonymised management-unit display labels only."""
from pathlib import Path
import pandas as pd
SRC = Path(__file__).resolve().parent.parent / "source_data"
UNRECORDED = "Unrecorded"

def unit_table():
    t = pd.read_csv(SRC / "ed3a_selection.csv")
    return t[t.grouping.eq("management unit (anonymised)")].drop(columns="grouping").rename(columns={"label":"unit"}).reset_index(drop=True)

def unit_letters():
    values = unit_table().unit
    mapping = {value:value for value in values if value != UNRECORDED}
    mapping["nan"] = UNRECORDED
    return mapping
