import json
import os
from pathlib import Path
from datetime import datetime, timezone


STATS_PATH = Path("assets/stats.json")
UPDATE_INTERVAL_MINUTES = int(os.getenv("UPDATE_INTERVAL_MINUTES", "73"))
FORCE_UPDATE = os.getenv("FORCE_UPDATE", "false").lower() == "true"
GITHUB_OUTPUT = os.getenv("GITHUB_OUTPUT")


def set_output(name, value):
    line = f"{name}={value}\n"

    if GITHUB_OUTPUT:
        with open(GITHUB_OUTPUT, "a", encoding="utf-8") as file:
            file.write(line)
    else:
        print(line, end="")


def main():
    if FORCE_UPDATE:
        print("Manual workflow run detected. Update will run now.")
        set_output("should_update", "true")
        return

    if not STATS_PATH.exists():
        print("stats.json does not exist. Update will run now.")
        set_output("should_update", "true")
        return

    try:
        data = json.loads(STATS_PATH.read_text(encoding="utf-8"))
        last_updated_iso = data.get("lastUpdatedIso")

        if not last_updated_iso:
            print("lastUpdatedIso is missing. Update will run now.")
            set_output("should_update", "true")
            return

        last_updated = datetime.fromisoformat(last_updated_iso)
        now = datetime.now(timezone.utc)

        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        minutes_since_update = (now - last_updated.astimezone(timezone.utc)).total_seconds() / 60

        print(f"Minutes since last update: {minutes_since_update:.1f}")
        print(f"Required interval: {UPDATE_INTERVAL_MINUTES} minutes")

        if minutes_since_update >= UPDATE_INTERVAL_MINUTES:
            set_output("should_update", "true")
        else:
            set_output("should_update", "false")

    except Exception as error:
        print(f"Could not check previous update time: {error}")
        print("Update will run now as a safe fallback.")
        set_output("should_update", "true")


if __name__ == "__main__":
    main()
