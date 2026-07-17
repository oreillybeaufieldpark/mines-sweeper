import re, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

session = requests.Session()

# Letters that NFKD won't decompose into ascii + combining mark
# (they're distinct letters, not accented forms) so map them by hand.
EXTRA_LETTER_MAP = str.maketrans({
    "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE",
    "ł": "l", "Ł": "L",
    "đ": "d", "Đ": "D",
    "ß": "ss",
})

def norm(s):
    s = str(s or "").translate(EXTRA_LETTER_MAP)
    s = unicodedata.normalize("NFKD", s)
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

def load_espn_players(event_id, league="pga"):
    base = f"https://sports.core.api.espn.com/v2/sports/golf/leagues/{league}/events/{event_id}/competitions/{event_id}"
    competitors_url = f"{base}/competitors?limit=200"

    items = get_json(competitors_url)["items"]
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
