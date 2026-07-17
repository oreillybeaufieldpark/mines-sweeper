import json, random
from pathlib import Path

import pandas as pd

from espn_data import load_espn_players

CONFIG = json.loads(Path("config.json").read_text(encoding="utf-8"))

EVENT_ID = CONFIG["event_id"]
LEAGUE = CONFIG.get("sport_league", "pga")
OWNERS_FILE = Path(CONFIG["owners_file"])
REDRAW_FILE = Path(CONFIG.get("redraw_owners_file", "owners_redraw.csv"))

def main():
    owners_df = pd.read_csv(OWNERS_FILE).dropna(subset=["Golfer"])
    owner_slots = [str(o).strip() for o in owners_df["Owner"]]
    top_n = len(owner_slots)

    espn_rows = load_espn_players(EVENT_ID, LEAGUE)

    made_cut = [r for r in espn_rows if r["thru"] != "CUT"]
    made_cut.sort(key=lambda r: (r["score_num"], r["order"]))

    if len(made_cut) < top_n:
        raise SystemExit(
            f"Only {len(made_cut)} players have made the cut so far, "
            f"need {top_n}. Wait until the cut is final before running this."
        )

    field = made_cut[:top_n]
    golfers = [r["espn_name"] for r in field]

    random.shuffle(golfers)
    random.shuffle(owner_slots)

    pairs = list(zip(golfers, owner_slots))
    pairs.sort(key=lambda p: p[0])

    out_df = pd.DataFrame(pairs, columns=["Golfer", "Owner"])
    out_df.to_csv(REDRAW_FILE, index=False)

    print(f"Top {top_n} players who made the cut, randomly redrawn to owners:\n")
    print(f"{'GOLFER':25} OWNER")
    print("-" * 50)
    for golfer, owner in sorted(pairs, key=lambda p: p[1]):
        print(f"{golfer[:25]:25} {owner}")

    print(f"\nWrote {REDRAW_FILE}")

if __name__ == "__main__":
    main()
