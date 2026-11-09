"""Redraw every manuscript figure from the repository's public resources."""
from pathlib import Path
import json
import runpy
import time
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIGURES = [
    "fig1_concept", "fig2_overview", "fig3_capture", "fig4_recovery",
    "fig5_spatial", "fig6_vehicles", "ed1_outage", "ed2_states",
    "ed3_matchable", "ed4_estimators", "ed5_spatial", "ed6_margins",
    "ed7_plates", "ed8_taxi_camera", "ed9_masking",
]


def main():
    names = FIGURES
    output = ROOT / "outputs" / "figures"
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for name in names:
        # Match a fresh plotting interpreter while retaining the same-process
        # audit hook. No child process can escape file-open instrumentation.
        plt.close("all")
        mpl.rcdefaults()
        started = time.monotonic()
        row = {"figure": name, "status": "running"}
        try:
            runpy.run_path(str(HERE / (name + ".py")), run_name="__main__")
            row["status"] = "completed"
        except BaseException as error:
            row.update(status="failed", error_type=type(error).__name__)
            raise
        finally:
            row["seconds"] = time.monotonic() - started
            results.append(row)
            (output / "render_manifest.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            plt.close("all")


if __name__ == "__main__":
    main()
