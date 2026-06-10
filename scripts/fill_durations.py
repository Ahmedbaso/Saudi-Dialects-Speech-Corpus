import os
import time
import subprocess
from urllib.parse import quote

import requests
from dotenv import load_dotenv


load_dotenv()

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Recordings")
ATTACHMENT_FIELD = os.getenv("ATTACHMENT_FIELD", "Attachments")
DURATION_FIELD = os.getenv("DURATION_FIELD", "Duration Seconds")


if not AIRTABLE_TOKEN:
    raise SystemExit("Missing AIRTABLE_TOKEN")

if not BASE_ID:
    raise SystemExit("Missing AIRTABLE_BASE_ID")


HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}

TABLE_ENCODED = quote(TABLE_NAME, safe="")
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ENCODED}"


def request_with_retry(method, url, **kwargs):
    max_attempts = 5

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as error:
            print(f"Request attempt {attempt}/{max_attempts} failed: {error}")

            if attempt == max_attempts:
                raise

            time.sleep(3 * attempt)


def get_duration_seconds(audio_url):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print("ffprobe error:", result.stderr.strip())
            return None

        output = result.stdout.strip()

        if not output:
            return None

        return round(float(output), 2)

    except Exception as error:
        print("Duration error:", error)
        return None


def fetch_records():
    records = []
    offset = None

    while True:
        params = {
            "pageSize": 100,
            "fields[]": [ATTACHMENT_FIELD, DURATION_FIELD],
        }

        if offset:
            params["offset"] = offset

        response = request_with_retry(
            "GET",
            BASE_URL,
            headers=HEADERS,
            params=params,
            timeout=90,
        )

        data = response.json()
        records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

        time.sleep(0.25)

    return records


def update_duration(record_id, duration):
    payload = {
        "fields": {
            DURATION_FIELD: duration
        }
    }

    try:
        request_with_retry(
            "PATCH",
            f"{BASE_URL}/{record_id}",
            headers=HEADERS,
            json=payload,
            timeout=90,
        )
        return True

    except requests.exceptions.RequestException as error:
        print(f"Failed to update Airtable record {record_id}: {error}")
        return False


def main():
    print("Fetching Airtable recording records...")
    records = fetch_records()
    print(f"Fetched recording records: {len(records)}")

    updated = 0
    skipped_existing = 0
    skipped_no_attachment = 0
    failed = 0

    for index, record in enumerate(records, start=1):
        record_id = record["id"]
        fields = record.get("fields", {})

        existing_duration = fields.get(DURATION_FIELD)

        if existing_duration not in (None, "", 0):
            skipped_existing += 1
            continue

        attachments = fields.get(ATTACHMENT_FIELD, [])

        if not attachments:
            skipped_no_attachment += 1
            continue

        attachment = attachments[0]
        audio_url = attachment.get("url")
        filename = attachment.get("filename", "unknown")

        if not audio_url:
            skipped_no_attachment += 1
            continue

        print(f"[{index}/{len(records)}] Checking: {filename}")

        duration = get_duration_seconds(audio_url)

        if duration is None:
            print(f"Failed to read duration: {filename}")
            failed += 1
            continue

        success = update_duration(record_id, duration)

        if success:
            updated += 1
            print(f"Updated: {filename} -> {duration} seconds")
        else:
            failed += 1
            print(f"Failed to update Airtable: {filename}")

        time.sleep(0.35)

    print("\nDuration update done.")
    print(f"Updated: {updated}")
    print(f"Skipped existing durations: {skipped_existing}")
    print(f"Skipped no attachment: {skipped_no_attachment}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
