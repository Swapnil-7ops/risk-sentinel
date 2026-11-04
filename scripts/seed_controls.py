"""Seed the ISO 27001 control catalogue manually; never run this at app startup."""

import json
from pathlib import Path

from app.services.control_service import seed_controls


if __name__ == "__main__":
    controls_path = Path(__file__).resolve().parents[1] / "data" / "iso27001_controls.json"
    with controls_path.open(encoding="utf-8") as file:
        controls = json.load(file)
    seed_controls(controls)
    print(f"Upserted {len(controls)} ISO 27001 controls.")
