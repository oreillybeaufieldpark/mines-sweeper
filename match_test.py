import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from rapidfuzz import process, fuzz

from espn_data import norm, load_espn_players

MIN_CONFIDENCE = 95

CONFIG = json.loads(Path("config.json").read_text(encoding="utf-8"))

EVENT_ID = CONFIG["event_id"]
LEAGUE = CONFIG.get("sport_league", "pga")
OWNERS_FILE = Path(CONFIG["owners_file"])
REDRAW_FILE = Path(CONFIG.get("redraw_owners_file", "owners_redraw.csv"))
OUT = Path(CONFIG["output_file"])

def build_owner_map(owners_file, keys, label):
    df = pd.read_csv(owners_file)
    df = df.rename(columns={c: str(c).strip() for c in df.columns})
    df = df.dropna(subset=["Golfer"])

    owner_map = {}
    unmatched = []

    for _, row in df.iterrows():
        golfer = str(row["Golfer"]).strip()
        owner = str(row["Owner"]).strip()

        match = process.extractOne(
            norm(golfer),
            keys,
            scorer=fuzz.WRatio
        )

        if not match or match[1] < MIN_CONFIDENCE:
            unmatched.append(golfer)
            continue

        key, confidence, _ = match
        owner_map[key] = owner

    if unmatched:
        print(f"WARNING: could not confidently match these {label} golfers to the ESPN field:")
        for g in unmatched:
            print(f"  - {g}")
        print()

    return owner_map

def main():
    espn_rows = load_espn_players(EVENT_ID, LEAGUE)

    choices = {
        norm(r["espn_name"]): r
        for r in espn_rows
    }
    keys = list(choices.keys())

    owner_map = build_owner_map(OWNERS_FILE, keys, "original")

    has_redraw = REDRAW_FILE.exists()
    redraw_map = (
        build_owner_map(REDRAW_FILE, keys, "redraw")
        if has_redraw else {}
    )

    players = []

    for key, espn in choices.items():
        players.append({
            "position": espn["position"],
            "score": espn["score"],
            "score_num": espn["score_num"],
            "thru": espn["thru"],
            "golfer": espn["espn_name"],
            "owner": owner_map.get(key, ""),
            "owner_redraw": redraw_map.get(key, ""),
            "order": espn["order"],
        })

    players.sort(
        key=lambda r: (
            r["score_num"],
            r["order"]
        )
    )

    print(f"{'POS':4} {'SCORE':>6} {'THRU':>6}  {'GOLFER':25} {'OWNER':20} REDRAW")
    print("-" * 110)

    for r in players:
        print(
            f"{r['position']:4} "
            f"{r['score']:>6} "
            f"{r['thru']:>6}  "
            f"{r['golfer'][:25]:25} "
            f"{r['owner']:20} "
            f"{r['owner_redraw']}"
        )

    output = {
        "event_name": CONFIG.get("event_name", ""),
        "page_title": CONFIG.get("page_title", CONFIG.get("event_name", "")),
        "generated_at": datetime.now(ZoneInfo("Europe/Dublin")).isoformat(),
        "has_redraw": has_redraw,
        "players": players,
    }

    OUT.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8"
    )

    print(f"\nWrote {OUT}")

if __name__ == "__main__":
    main()
