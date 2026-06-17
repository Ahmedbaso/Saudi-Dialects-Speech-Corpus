import os
import re
import json
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv


load_dotenv()

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")

PARTICIPANTS_TABLE = "Participants"
RECORDINGS_TABLE = "Recordings"
AGE_FIELD = "Age"
ADMINISTRATIVE_REGION_FIELD = "Administrative Region"


ADMINISTRATIVE_REGION_NAMES = [
    "Riyadh",
    "Makkah",
    "Madinah",
    "Eastern Province",
    "Qassim",
    "Hail",
    "Tabuk",
    "Northern Borders",
    "Jazan",
    "Najran",
    "Al Bahah",
    "Al Jawf",
    "Asir",
]

ADMINISTRATIVE_REGION_ALIASES = {
    "riyadh": "Riyadh",
    "ar riyad": "Riyadh",
    "ar riyadh": "Riyadh",
    "al riyadh": "Riyadh",
    "منطقة الرياض": "Riyadh",
    "الرياض": "Riyadh",

    "makkah": "Makkah",
    "mecca": "Makkah",
    "makkah al mukarramah": "Makkah",
    "منطقة مكة المكرمة": "Makkah",
    "مكة المكرمة": "Makkah",
    "مكة": "Makkah",

    "madinah": "Madinah",
    "medina": "Madinah",
    "al madinah": "Madinah",
    "al madinah al munawwarah": "Madinah",
    "منطقة المدينة المنورة": "Madinah",
    "المدينة المنورة": "Madinah",
    "المدينة": "Madinah",

    "eastern province": "Eastern Province",
    "eastern": "Eastern Province",
    "ash sharqiyah": "Eastern Province",
    "al sharqiyah": "Eastern Province",
    "منطقة الشرقية": "Eastern Province",
    "المنطقة الشرقية": "Eastern Province",
    "الشرقية": "Eastern Province",

    "qassim": "Qassim",
    "al qassim": "Qassim",
    "al quassim": "Qassim",
    "منطقة القصيم": "Qassim",
    "القصيم": "Qassim",

    "hail": "Hail",
    "ha'il": "Hail",
    "ha il": "Hail",
    "حائل": "Hail",
    "منطقة حائل": "Hail",

    "tabuk": "Tabuk",
    "تبوك": "Tabuk",
    "منطقة تبوك": "Tabuk",

    "northern borders": "Northern Borders",
    "northern border": "Northern Borders",
    "al hudud ash shamaliyah": "Northern Borders",
    "منطقة الحدود الشمالية": "Northern Borders",
    "الحدود الشمالية": "Northern Borders",

    "jazan": "Jazan",
    "jizan": "Jazan",
    "جازان": "Jazan",
    "جيزان": "Jazan",
    "منطقة جازان": "Jazan",

    "najran": "Najran",
    "نجران": "Najran",
    "منطقة نجران": "Najran",

    "al bahah": "Al Bahah",
    "bahah": "Al Bahah",
    "الباحة": "Al Bahah",
    "منطقة الباحة": "Al Bahah",

    "al jawf": "Al Jawf",
    "jawf": "Al Jawf",
    "الجوف": "Al Jawf",
    "منطقة الجوف": "Al Jawf",

    "asir": "Asir",
    "aseer": "Asir",
    "`asir": "Asir",
    "عسير": "Asir",
    "منطقة عسير": "Asir",
}


if not AIRTABLE_TOKEN:
    raise SystemExit("Missing AIRTABLE_TOKEN")

if not BASE_ID:
    raise SystemExit("Missing AIRTABLE_BASE_ID")


HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}


def airtable_url(table_name):
    table_encoded = quote(table_name, safe="")
    return f"https://api.airtable.com/v0/{BASE_ID}/{table_encoded}"


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


def fetch_all_records(table_name, fields=None):
    records = []
    offset = None

    while True:
        params = {
            "pageSize": 100
        }

        if fields:
            params["fields[]"] = fields

        if offset:
            params["offset"] = offset

        response = request_with_retry(
            "GET",
            airtable_url(table_name),
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


def normalize(value):
    if value is None:
        return ""

    if isinstance(value, list):
        return " ".join(str(item) for item in value).strip().lower()

    return str(value).strip().lower()


def count_gender(participants):
    male = 0
    female = 0

    for record in participants:
        fields = record.get("fields", {})
        gender = normalize(fields.get("Gender"))

        if gender in ["male", "m", "ذكر"]:
            male += 1
        elif gender in ["female", "f", "أنثى", "انثى"]:
            female += 1

    return male, female


def count_devices(participants):
    iphone = 0
    android = 0

    for record in participants:
        fields = record.get("fields", {})
        device = normalize(fields.get("Device Type"))

        if "iphone" in device or "ios" in device:
            iphone += 1
        elif "android" in device:
            android += 1

    return iphone, android


def count_regions(participants):
    regions = {
        "Central": 0,
        "Western": 0,
        "Southern": 0,
        "Eastern": 0,
        "Northern": 0
    }

    for record in participants:
        fields = record.get("fields", {})
        region = str(fields.get("Region", "")).strip()

        if not region:
            continue

        matched = False
        for key in regions:
            if region.lower() == key.lower():
                regions[key] += 1
                matched = True
                break

        if not matched:
            regions[region] = regions.get(region, 0) + 1

    return regions


def count_age_groups(participants):
    age_counts = Counter()

    for record in participants:
        fields = record.get("fields", {})
        age_group = get_first_list_value(fields.get(AGE_FIELD))

        if age_group:
            age_counts[age_group] += 1

    return dict(age_counts)


def get_most_common_age_group(participants):
    age_groups = count_age_groups(participants)

    if not age_groups:
        return "", 0, {}

    most_common_age_group, most_common_age_count = sorted(
        age_groups.items(),
        key=lambda item: (-item[1], item[0])
    )[0]

    return most_common_age_group, most_common_age_count, age_groups


def normalize_administrative_region(value):
    region = get_first_list_value(value)

    if not region:
        return ""

    key = normalize(region)
    return ADMINISTRATIVE_REGION_ALIASES.get(key, region)


def count_administrative_regions(participants):
    administrative_regions = {region_name: 0 for region_name in ADMINISTRATIVE_REGION_NAMES}

    for record in participants:
        fields = record.get("fields", {})
        region = normalize_administrative_region(fields.get(ADMINISTRATIVE_REGION_FIELD))

        if not region:
            continue

        administrative_regions[region] = administrative_regions.get(region, 0) + 1

    return administrative_regions


def get_administrative_region_summary(participants):
    administrative_regions = count_administrative_regions(participants)
    represented = sum(1 for count in administrative_regions.values() if count > 0)

    return administrative_regions, represented, len(ADMINISTRATIVE_REGION_NAMES)


def count_free_speech(recordings, participants):
    s31_count = 0

    for record in recordings:
        fields = record.get("fields", {})
        name = str(fields.get("Name", ""))

        if "_S31_" in name or "S31" in name:
            s31_count += 1

    if s31_count > 0:
        return s31_count

    fallback_count = 0

    for record in participants:
        fields = record.get("fields", {})
        free_topic = str(fields.get("Free Topic", "")).strip()

        if free_topic and free_topic.lower() != "skipped":
            fallback_count += 1

    return fallback_count


def count_completed_sessions(participants):
    completed = 0

    for record in participants:
        fields = record.get("fields", {})
        linked_recordings = fields.get("Recordings")

        if isinstance(linked_recordings, list) and len(linked_recordings) > 0:
            completed += 1
        elif "Recordings" not in fields:
            completed += 1

    return completed


def get_duration_seconds(record):
    fields = record.get("fields", {})
    duration = fields.get("Duration Seconds")

    try:
        return float(duration or 0)
    except (ValueError, TypeError):
        return 0


def calculate_total_minutes(recordings):
    total_seconds = 0

    for record in recordings:
        total_seconds += get_duration_seconds(record)

    return round(total_seconds / 60, 1)


def count_total_recordings(recordings):
    count_with_attachments = 0

    for record in recordings:
        fields = record.get("fields", {})
        attachments = fields.get("Attachments")

        if isinstance(attachments, list) and len(attachments) > 0:
            count_with_attachments += 1

    if count_with_attachments > 0:
        return count_with_attachments

    return len(recordings)


def get_first_list_value(value):
    if isinstance(value, list) and len(value) > 0:
        return str(value[0]).strip()

    if value is None:
        return ""

    return str(value).strip()


def extract_spkid_from_name(name):
    match = re.search(r"SPK\d{4}", str(name))
    if match:
        return match.group(0)

    return ""


def get_recording_spkid(record):
    fields = record.get("fields", {})

    linked_spkid = get_first_list_value(fields.get("SPKID (from Speaker Link)"))
    if linked_spkid:
        return linked_spkid

    name_spkid = extract_spkid_from_name(fields.get("Name", ""))
    if name_spkid:
        return name_spkid

    return ""


def calculate_duration_bins(recordings):
    participant_seconds = {}

    for record in recordings:
        fields = record.get("fields", {})
        attachments = fields.get("Attachments")

        if not isinstance(attachments, list) or len(attachments) == 0:
            continue

        spkid = get_recording_spkid(record)
        if not spkid:
            continue

        duration_seconds = get_duration_seconds(record)
        if duration_seconds <= 0:
            continue

        participant_seconds[spkid] = participant_seconds.get(spkid, 0) + duration_seconds

    duration_bins = {
        "< 1 min": 0,
        "1-2 min": 0,
        "2-3 min": 0,
        "3+ min": 0
    }

    for total_seconds in participant_seconds.values():
        total_minutes = total_seconds / 60

        if total_minutes < 1:
            duration_bins["< 1 min"] += 1
        elif total_minutes < 2:
            duration_bins["1-2 min"] += 1
        elif total_minutes < 3:
            duration_bins["2-3 min"] += 1
        else:
            duration_bins["3+ min"] += 1

    return duration_bins


def main():
    print("Fetching Participants...")
    participants = fetch_all_records(
        PARTICIPANTS_TABLE,
        fields=[
            "Gender",
            "Device Type",
            "Region",
            AGE_FIELD,
                        ADMINISTRATIVE_REGION_FIELD,
"Recordings",
            "Free Topic"
        ]
    )

    print("Fetching Recordings...")
    recordings = fetch_all_records(
        RECORDINGS_TABLE,
        fields=[
            "Name",
            "Attachments",
            "Duration Seconds",
            "SPKID (from Speaker Link)"
        ]
    )

    total_participants = len(participants)
    total_recordings = count_total_recordings(recordings)
    total_minutes = calculate_total_minutes(recordings)

    male_participants, female_participants = count_gender(participants)
    iphone_users, android_users = count_devices(participants)
    regions = count_regions(participants)
    administrative_regions, administrative_regions_represented, administrative_regions_total = get_administrative_region_summary(participants)
    free_speech_samples = count_free_speech(recordings, participants)
    completed_sessions = count_completed_sessions(participants)
    duration_bins = calculate_duration_bins(recordings)
    most_common_age_group, most_common_age_group_count, age_groups = get_most_common_age_group(participants)

    now_ksa = datetime.now(ZoneInfo("Asia/Riyadh"))

    stats = {
        "totalParticipants": total_participants,
        "totalRecordings": total_recordings,
        "totalMinutes": total_minutes,
        "maleParticipants": male_participants,
        "femaleParticipants": female_participants,
        "freeSpeechSamples": free_speech_samples,
        "completedSessions": completed_sessions,
        "mostCommonAgeGroup": most_common_age_group,
        "mostCommonAgeGroupCount": most_common_age_group_count,
        "ageGroups": age_groups,
        "iphoneUsers": iphone_users,
        "androidUsers": android_users,
        "regions": regions,
        "administrativeRegions": administrative_regions,
        "administrativeRegionsRepresented": administrative_regions_represented,
        "administrativeRegionsTotal": administrative_regions_total,
        "durationBins": duration_bins,
        "lastUpdated": now_ksa.strftime("%Y-%m-%d %H:%M KSA"),
        "lastUpdatedIso": now_ksa.isoformat()
    }

    output_dir = Path("assets")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / "stats.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(stats, file, ensure_ascii=False, indent=2)

    print("\nGenerated stats:")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
