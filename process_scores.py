import json, sys
from datetime import datetime, timezone

NAME_MAP = {
    "France": "France", "Spain": "Spain", "Argentina": "Argentina",
    "England": "England", "Brazil": "Brazil", "Germany": "Germany",
    "Portugal": "Portugal", "Morocco": "Morocco",
    "Netherlands": "Netherlands", "Colombia": "Colombia",
    "Belgium": "Belgium", "Uruguay": "Uruguay",
    "Japan": "Japan", "Senegal": "Senegal",
    "Croatia": "Croatia", "Norway": "Norway",
    "United States": "USA", "Mexico": "Mexico",
    "Switzerland": "Switzerland", "Austria": "Austria",
    "Korea Republic": "South Korea", "Ecuador": "Ecuador",
    "Turkiye": "Turkey", "Turkey": "Turkey",
    "Australia": "Australia", "Scotland": "Scotland",
    "Sweden": "Sweden", "Czechia": "Czechia",
    "Algeria": "Algeria", "Egypt": "Egypt",
    "Iran": "Iran", "Paraguay": "Paraguay",
    "Bosnia and Herzegovina": "Bosnia",
    "Canada": "Canada",
    "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast",
    "Ghana": "Ghana", "Tunisia": "Tunisia",
    "South Africa": "South Africa", "Saudi Arabia": "Saudi Arabia",
    "Iraq": "Iraq", "Panama": "Panama",
    "DR Congo": "DR Congo", "Congo DR": "DR Congo",
    "Democratic Republic of Congo": "DR Congo",
    "Qatar": "Qatar", "Jordan": "Jordan",
    "Uzbekistan": "Uzbekistan",
    "Cabo Verde": "Cape Verde", "Cape Verde": "Cape Verde",
    "Curaçao": "Curacao", "Curacao": "Curacao",
    "Haiti": "Haiti", "New Zealand": "New Zealand",
}

def norm(api_name):
    return NAME_MAP.get(api_name, api_name)

teams = {}

# ── 1. Group standings ────────────────────────────────────────────────────────
try:
    with open("standings_raw.json") as f:
        data = json.load(f)

    for group in data.get("standings", []):
        table = group.get("table", [])
        for idx, row in enumerate(table):
            api_name = row.get("team", {}).get("name", "")
            name = norm(api_name)
            if not name:
                continue
            if name not in teams:
                teams[name] = {}
            teams[name]["group"] = group.get("group", "").replace("GROUP_", "")
            teams[name]["played"] = row.get("playedGames", 0)
            teams[name]["points"] = row.get("points", 0)
            teams[name]["gf"] = row.get("goalsFor", 0)
            teams[name]["ga"] = row.get("goalsAgainst", 0)
            if idx == 0 and row.get("points") is not None:
                teams[name]["group_winner"] = True
except Exception as e:
    print(f"Warning: standings processing failed: {e}", file=sys.stderr)

# ── 2. Matches (all stages) ───────────────────────────────────────────────────
stage = "group_stage"
golden_boot = None

STAGE_MAP = {
    "GROUP_STAGE": "group_stage",
    "ROUND_OF_32": "round_of_32",
    "LAST_32": "round_of_32",
    "ROUND_OF_16": "round_of_16",
    "LAST_16": "round_of_16",
    "QUARTER_FINALS": "quarter_final",
    "SEMI_FINALS": "semi_final",
    "THIRD_PLACE": "third_place",
    "FINAL": "final",
}

STAGE_ORDER = [
    "group_stage", "round_of_32", "round_of_16",
    "quarter_final", "semi_final", "final", "complete"
]

try:
    with open("matches_raw.json") as f:
        mdata = json.load(f)

    for m in mdata.get("matches", []):
        s = m.get("stage", "")
        status = m.get("status", "")
        home_api = m.get("homeTeam", {}).get("name", "")
        away_api = m.get("awayTeam", {}).get("name", "")
        home = norm(home_api)
        away = norm(away_api)
        winner = m.get("score", {}).get("winner")  # HOME_TEAM, AWAY_TEAM, DRAW, None

        if not home or not away:
            continue

        if home not in teams:
            teams[home] = {}
        if away not in teams:
            teams[away] = {}

        mapped_stage = STAGE_MAP.get(s, "")
        if not mapped_stage:
            continue

        # Update highest stage we've seen
        if mapped_stage in STAGE_ORDER:
            if STAGE_ORDER.index(mapped_stage) > STAGE_ORDER.index(stage):
                stage = mapped_stage

        if mapped_stage == "group_stage":
            continue  # handled by standings above

        # Mark teams as having reached this round
        for field, stages_needed in [
            ("round_of_32", ["round_of_32"]),
            ("round_of_16", ["round_of_16"]),
            ("quarter_final", ["quarter_final"]),
            ("semi_final", ["semi_final"]),
            ("finalist", ["final"]),
        ]:
            if mapped_stage in stages_needed:
                teams[home][field] = True
                teams[away][field] = True

        # Handle finished knockouts
        if status == "FINISHED":
            if mapped_stage in ["round_of_32", "round_of_16", "quarter_final", "semi_final"]:
                if winner == "HOME_TEAM":
                    teams[away]["eliminated"] = True
                elif winner == "AWAY_TEAM":
                    teams[home]["eliminated"] = True

            elif mapped_stage == "third_place":
                if winner == "HOME_TEAM":
                    teams[home]["third_place"] = True
                    teams[away]["eliminated"] = True
                elif winner == "AWAY_TEAM":
                    teams[away]["third_place"] = True
                    teams[home]["eliminated"] = True

            elif mapped_stage == "final":
                stage = "complete"
                if winner == "HOME_TEAM":
                    teams[home]["winner"] = True
                    teams[away]["eliminated"] = True
                elif winner == "AWAY_TEAM":
                    teams[away]["winner"] = True
                    teams[home]["eliminated"] = True

    # Mark teams eliminated from group stage once knockouts have started
    if stage != "group_stage":
        for name, t in teams.items():
            if name.startswith("_"):
                continue
            if not t.get("round_of_32") and not t.get("eliminated"):
                t["eliminated"] = True

    # Top scorers (golden boot) — available in some plans
    scorers = mdata.get("scorers", [])
    if scorers:
        top = scorers[0]
        golden_boot = norm(top.get("team", {}).get("name", ""))

except Exception as e:
    print(f"Warning: matches processing failed: {e}", file=sys.stderr)

# ── 3. Write scores.json ──────────────────────────────────────────────────────
output = {
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
    "stage": stage,
    "golden_boot_team": golden_boot,
    "teams": teams,
}

with open("scores.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"scores.json written — stage={stage}, teams={len(teams)}")
