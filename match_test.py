import json, re, unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from rapidfuzz import process, fuzz

EVENT_ID = "401811947"
XLSX = Path("Major Golf Sweepstakes-7.xlsx")
OUT = Path("matched_leaderboard.json")

BASE = f"https://sports.core.api.espn.com/v2/sports/golf/leagues/pga/events/{EVENT_ID}/competitions/{EVENT_ID}"
COMPETITORS_URL = f"{BASE}/competitors?limit=200"

session = requests.Session()

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def get_json(url):
    return session.get(
        url.replace("http://", "https://"),
        timeout=10
    ).json()

def score_to_num(score):
    if score in (None, "", "E"):
        return 0
    return int(str(score).replace("+", ""))

def irish_tee_time(status):
    tee = status.get("teeTime")
    if not tee:
        return ""

    try:
        dt = datetime.fromisoformat(
            tee.replace("Z", "+00:00")
        )
        ie = dt.astimezone(
            ZoneInfo("Europe/Dublin")
        )
        return ie.strftime("%H:%M")
    except Exception:
        return ""

def display_thru(status, score_display):
    typ = status.get("type", {})
    state = typ.get("state")

    try:
        score_num = (
            0 if score_display == "E"
            else int(str(score_display).replace("+", ""))
        )
    except:
        score_num = 999

    if score_num > 4:
        return "CUT"

    if typ.get("completed"):
        return "F"

    if state == "in" and status.get("thru") not in (None, "", 0):
        return str(status.get("thru"))

    return irish_tee_time(status)

def load_one(item):
    athlete = get_json(item["athlete"]["$ref"])
    score = get_json(item["score"]["$ref"])
    status = get_json(item["status"]["$ref"])

    return {
        "espn_name": athlete.get("displayName", ""),
        "score": score.get("displayValue", ""),
        "score_num": score_to_num(
            score.get("displayValue", "")
        ),
        "position": status.get(
            "position", {}
        ).get("displayName", ""),
        "thru": display_thru(
            status,
            score.get("displayValue", "")
        ),
        "order": item.get("order", 9999),
    }

def load_espn_players():
    items = get_json(COMPETITORS_URL)["items"]
    rows = []

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [
            ex.submit(load_one, item)
            for item in items
        ]

        for fut in as_completed(futures):
            try:
                row = fut.result()
                if row["espn_name"]:
                    rows.append(row)
            except Exception as e:
                print("Skipping one player:", e)

    return rows

def main():
    espn_rows = load_espn_players()

    df = pd.read_excel(XLSX)
    df = df.rename(
        columns={c: str(c).strip() for c in df.columns}
    )
    df = df.dropna(subset=["Golfer"])

    choices = {
        norm(r["espn_name"]): r
        for r in espn_rows
    }

    keys = list(choices.keys())

    owner_map = {}

    for _, row in df.iterrows():
        golfer = str(row["Golfer"]).strip()
        owner = str(row["Owner"]).strip()

        match = process.extractOne(
            norm(golfer),
            keys,
            scorer=fuzz.WRatio
        )

        if not match:
            continue

        key, confidence, _ = match
        owner_map[key] = owner

    output = []

    for key, espn in choices.items():
        output.append({
            "position": espn["position"],
            "score": espn["score"],
            "score_num": espn["score_num"],
            "thru": espn["thru"],
            "golfer": espn["espn_name"],
            "owner": owner_map.get(key, ""),
            "order": espn["order"],
        })

    output.sort(
        key=lambda r: (
            r["score_num"],
            r["order"]
        )
    )

    print(f"{'POS':4} {'SCORE':>6} {'THRU':>6}  {'GOLFER':25} OWNER")
    print("-" * 90)

    for r in output:
        print(
            f"{r['position']:4} "
            f"{r['score']:>6} "
            f"{r['thru']:>6}  "
            f"{r['golfer'][:25]:25} "
            f"{r['owner']}"
        )

    OUT.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    print(f"\nWrote {OUT}")

if __name__ == "__main__":
    main()
