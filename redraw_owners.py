import json, random
from pathlib import Path

import pandas as pd

from espn_data import load_espn_players

CONFIG = json.loads(Path("config.json").read_text(encoding="utf-8"))

EVENT_ID = CONFIG["event_id"]
LEAGUE = CONFIG.get("sport_league", "pga")
OWNERS_FILE = Path(CONFIG["owners_file"])
REDRAW_FILE = Path(CONFIG.get("redraw_owners_file", "owners_redraw.csv"))

STILL_PLAYING = {"STATUS_IN_PROGRESS", "STATUS_SCHEDULED"}

def main():
    owners_df = pd.read_csv(OWNERS_FILE).dropna(subset=["Golfer"])
    # Preserve first-seen order rather than sorting, just for stable,
    # readable tier printouts; the actual pairing is randomized below.
    owners = list(dict.fromkeys(str(o).strip() for o in owners_df["Owner"]))
    n_owners = len(owners)

    espn_rows = load_espn_players(EVENT_ID, LEAGUE)

    unfinished = [r["espn_name"] for r in espn_rows if r["status_type"] in STILL_PLAYING]
    if unfinished:
        raise SystemExit(
            "The cut isn't official yet - these players are still playing "
            f"or haven't teed off: {', '.join(unfinished[:10])}"
            + (f" (+{len(unfinished) - 10} more)" if len(unfinished) > 10 else "")
        )

    made_cut = [r for r in espn_rows if r["status_type"] != "STATUS_CUT"]
    made_cut.sort(key=lambda r: (r["score_num"], r["order"]))

    print(f"{len(made_cut)} of {len(espn_rows)} players made the cut (per ESPN's own cut status)")

    per_owner = len(made_cut) // n_owners
    if per_owner < 1:
        raise SystemExit(
            f"Only {len(made_cut)} players made the cut, not enough for "
            f"{n_owners} owners to get even one each."
        )

    total_drawn = per_owner * n_owners
    left_out = len(made_cut) - total_drawn
    print(
        f"{n_owners} owners x {per_owner} each = {total_drawn} players drawn "
        f"({left_out} lowest-ranked left out to divide evenly)\n"
    )

    field = made_cut[:total_drawn]

    # Draw in ranked tiers of n_owners (top n_owners, then next n_owners,
    # ...) so every owner gets exactly one player from each skill tier,
    # with the pairing within each tier randomized independently.
    pairs = []
    for tier_num, start in enumerate(range(0, total_drawn, n_owners), start=1):
        tier = field[start:start + n_owners]
        tier_golfers = [r["espn_name"] for r in tier]
        tier_owners = owners.copy()
        random.shuffle(tier_golfers)
        random.shuffle(tier_owners)

        tier_pairs = list(zip(tier_golfers, tier_owners))
        pairs.extend(tier_pairs)

        print(f"Tier {tier_num} (ranks {start + 1}-{start + len(tier)}):")
        for golfer, owner in sorted(tier_pairs, key=lambda p: p[1]):
            print(f"  {golfer[:25]:25} {owner}")
        print()

    out_df = pd.DataFrame(pairs, columns=["Golfer", "Owner"])
    out_df.to_csv(REDRAW_FILE, index=False)

    print(f"Wrote {REDRAW_FILE}")

if __name__ == "__main__":
    main()
