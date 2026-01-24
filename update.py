import requests
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime

# --- CONFIGURATION ---
# Base RTP estimates (Return To Player)
RTP_CONFIG = {
    "LOTTO": 0.23, "VIKING": 0.25, "EJACKPOT": 0.32,
    "POWERBALL": 0.15, "MEGAMILLIONS": 0.15, "EUROMILLIONS": 0.20
}

ODDS_CONFIG = {
    "LOTTO": 18643560, "VIKING": 61357560, "EJACKPOT": 139838160,
    "POWERBALL": 292201338, "MEGAMILLIONS": 302575350, "EUROMILLIONS": 139838160
}

NAMES = {
    "LOTTO": "Finnish Lotto",
    "VIKING": "Viking lotto",
    "EJACKPOT": "Eurojackpot",
    "POWERBALL": "US Powerball",
    "MEGAMILLIONS": "Mega Millions",
    "EUROMILLIONS": "EuroMillions"
}

USER_AGENT = "Mozilla/5.0 (LottoBot/1.0)"

# --- DATA FETCHERS ---

def _safe_get_json(url, timeout=10):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    if not resp.ok:
        return None
    return resp.json()

def _safe_get_text(url, timeout=10):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    if not resp.ok:
        return None
    return resp.text

def _parse_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    digits = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None

def fetch_veikkaus(game_id):
    """Fetches official Finnish data for Lotto, Viking, Eurojackpot"""
    url = f"https://www.veikkaus.fi/api/draw-open-games/v1/games/{game_id}/draws"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        if not resp.ok:
            return None
        data = resp.json()
        if not data:
            return None

        draw = data[0]
        # Veikkaus returns cents (1000 = EUR 10.00)
        jackpot_cents = 0
        if draw.get("jackpots"):
            jackpot_cents = draw["jackpots"][0]["amount"]
        price_cents = draw["gameRuleSet"]["basePrice"]
        draw_time = draw["drawTime"]

        return {
            "name": draw.get("brandName") or NAMES[game_id],
            "jackpot": jackpot_cents / 100,
            "price": price_cents / 100,
            "next_draw": datetime.fromtimestamp(draw_time / 1000).strftime("%Y-%m-%d %H:%M"),
            "currency": "€",
            "odds_jackpot": ODDS_CONFIG[game_id],
            "base_rtp": RTP_CONFIG[game_id]
        }
    except Exception as e:
        print(f"⚠️ Veikkaus {game_id} failed: {e}")
        return None

def fetch_mass_lottery():
    """Fetches US Powerball & Mega Millions from Mass Lottery (Clean JSON)"""
    # This endpoint returns ALL games including multi-state ones
    url = "https://www.masslottery.com/rest/games/games"
    results = {}

    try:
        data = _safe_get_json(url)
        if not isinstance(data, list):
            return {}

        # Helper to find specific game in the list
        def extract_game(api_name, internal_name):
            for game in data:
                game_id = (game.get("game_id") or game.get("gameId") or game.get("id") or "").upper()
                if game_id == api_name:
                    jackpot = (
                        _parse_number(game.get("jackpot")) or
                        _parse_number(game.get("estimated_jackpot")) or
                        _parse_number(game.get("jackpotAmount"))
                    )
                    if jackpot is None:
                        return None
                    return {
                        "name": internal_name,
                        "jackpot": jackpot,
                        "price": 2.00,
                        "next_draw": game.get("next_draw_date") or game.get("nextDrawDate") or "Unknown",
                        "currency": "$",
                        "odds_jackpot": ODDS_CONFIG["POWERBALL" if api_name == "DB" else "MEGAMILLIONS"],
                        "base_rtp": RTP_CONFIG["POWERBALL" if api_name == "DB" else "MEGAMILLIONS"]
                    }
            return None

        # "DB" is Powerball, "MEGA" is Mega Millions in their system
        results["POWERBALL"] = extract_game("DB", NAMES["POWERBALL"])
        results["MEGAMILLIONS"] = extract_game("MEGA", NAMES["MEGAMILLIONS"])

    except Exception as e:
        print(f"⚠️ Mass Lottery failed: {e}")

    return results

def fetch_euromillions():
    """Fetches EuroMillions from UK National Lottery XML"""
    # XML is often more stable than undocumented JSON APIs
    url = "https://www.national-lottery.co.uk/results/euromillions/draw-history/xml"

    try:
        xml_text = _safe_get_text(url)
        if not xml_text:
            return fetch_euromillions_scrape()

        root = ET.fromstring(xml_text)
        latest_draw = root.find(".//draw")
        if latest_draw is None:
            return fetch_euromillions_scrape()

        jackpot = None
        for tag in ("jackpot", "jackpot-amount", "jackpot_amount", "jackpotAmount"):
            elem = latest_draw.find(tag)
            if elem is not None and elem.text:
                jackpot = _parse_number(elem.text)
                break

        draw_date = (
            latest_draw.findtext("draw-date") or
            latest_draw.findtext("drawDate") or
            latest_draw.findtext("date")
        )

        if jackpot is None:
            return fetch_euromillions_scrape()

        return {
            "name": NAMES["EUROMILLIONS"],
            "jackpot": jackpot,
            "price": 2.50,
            "next_draw": draw_date or "Unknown",
            "currency": "€",
            "odds_jackpot": ODDS_CONFIG["EUROMILLIONS"],
            "base_rtp": RTP_CONFIG["EUROMILLIONS"]
        }
    except Exception as e:
        print(f"⚠️ EuroMillions XML failed: {e}")
        return fetch_euromillions_scrape()

def fetch_euromillions_scrape():
    """Backup: Quick scrape of a lightweight results site"""
    try:
        # Lottoland's public API is often open
        url = "https://www.lottoland.com/api/drawings/euromillions"
        data = _safe_get_json(url)
        if not isinstance(data, dict):
            return None

        next_draw = data.get("next", {})
        jackpot_eur = (
            next_draw.get("jackpot", {}).get("amount") or
            next_draw.get("jackpotAmount")
        )
        date_str = (
            next_draw.get("date", {}).get("full") or
            next_draw.get("date") or
            ""
        )

        jackpot_value = _parse_number(jackpot_eur)
        if jackpot_value is None:
            return None

        # Lottoland sometimes returns cents for large values
        if jackpot_value > 1_000_000_000:
            jackpot_value = jackpot_value / 100

        return {
            "name": NAMES["EUROMILLIONS"],
            "jackpot": jackpot_value,
            "price": 2.50,
            "next_draw": date_str or "Unknown",
            "currency": "€",
            "odds_jackpot": ODDS_CONFIG["EUROMILLIONS"],
            "base_rtp": RTP_CONFIG["EUROMILLIONS"]
        }
    except Exception:
        return None

# --- MAIN CONTROLLER ---

def update_database():
    games_list = []
    print("--- Starting Update Job ---")

    # 1. VEIKKAUS (Finland)
    for gid in ["LOTTO", "VIKING", "EJACKPOT"]:
        data = fetch_veikkaus(gid)
        if data:
            games_list.append(data)
            print(f"✅ Success: {data['name']} (€{data['jackpot']:,.0f})")
        else:
            print(f"❌ Failed to fetch {gid}")
        time.sleep(1) # Be polite to the API

    # 2. MASS LOTTERY (USA)
    us_data = fetch_mass_lottery()
    if us_data.get("POWERBALL"):
        games_list.append(us_data["POWERBALL"])
    if us_data.get("MEGAMILLIONS"):
        games_list.append(us_data["MEGAMILLIONS"])

    # 3. EUROMILLIONS (Europe)
    em = fetch_euromillions()
    if em:
        games_list.append(em)

    # SAVE TO FILE
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "games": games_list
    }

    with open("lottery_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"✅ Updated {len(games_list)} lotteries successfully.")

if __name__ == "__main__":
    update_database()