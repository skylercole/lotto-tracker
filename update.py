import requests
import json
import time
from datetime import datetime
import re

# CONFIGURATION
# Base RTP estimates (Non-jackpot return to player)
RTP_CONFIG = {
    "LOTTO": 0.23,   # Finnish Lotto
    "VIKING": 0.25,  # Vikinglotto
    "EJACKPOT": 0.32, # Eurojackpot
    # International benchmarks (RTP varies by market/state)
    "POWERBALL": None,
    "MEGAMILLIONS": None,
    "EUROMILLIONS": None
}

ODDS_CONFIG = {
    "LOTTO": 18643560,
    "VIKING": 61357560,
    "EJACKPOT": 139838160,
    "POWERBALL": 292201338,
    "MEGAMILLIONS": 302575350,
    "EUROMILLIONS": 139838160
}

NAMES = {
    "LOTTO": "Finnish Lotto",
    "VIKING": "Viking lotto",
    "EJACKPOT": "Eurojackpot",
    "POWERBALL": "US Powerball",
    "MEGAMILLIONS": "Mega Millions",
    "EUROMILLIONS": "EuroMillions"
}

def _safe_get(url, headers=None, timeout=10, retries=2, backoff=2, expect_json=True):
    last_response = None
    for attempt in range(retries + 1):
        response = requests.get(url, headers=headers, timeout=timeout)
        last_response = response
        if response.status_code == 429 and attempt < retries:
            retry_after = response.headers.get("Retry-After")
            sleep_seconds = int(retry_after) if retry_after and retry_after.isdigit() else backoff * (attempt + 1)
            time.sleep(sleep_seconds)
            continue
        response.raise_for_status()
        return response.json() if expect_json else response.text
    if last_response is not None:
        last_response.raise_for_status()
    return None

def _parse_money(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().replace(",", "")
    # Handle formats like "$450 Million", "€250m", "450000000"
    multiplier = 1
    if ("billion" in text) or text.endswith("b"):
        multiplier = 1_000_000_000
    elif ("million" in text) or text.endswith("m"):
        multiplier = 1_000_000
    elif ("thousand" in text) or text.endswith("k"):
        multiplier = 1_000
    digits = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    try:
        return float(digits) * multiplier if digits else None
    except ValueError:
        return None

def _extract_jackpot_from_text(text):
    if not text:
        return None
    patterns = [
        r"Estimated Jackpot\s*\$?\s*([0-9,.]+)\s*(Billion|Million|B|M)?",
        r"Jackpot\s*\$?\s*([0-9,.]+)\s*(Billion|Million|B|M)?"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = match.group(1)
            unit = (match.group(2) or "").lower()
            if unit in ("billion", "b"):
                return _parse_money(f"{amount}b")
            if unit in ("million", "m"):
                return _parse_money(f"{amount}m")
            return _parse_money(amount)
    return None

def _first_list_item(payload):
    if isinstance(payload, list):
        return payload[0] if payload else None
    if isinstance(payload, dict):
        for key in ("data", "results", "draws"):
            items = payload.get(key)
            if isinstance(items, list) and items:
                return items[0]
    return None

def fetch_game_data(game_id):
    url = f"https://www.veikkaus.fi/api/draw-open-games/v1/games/{game_id}/draws"
    headers = {"User-Agent": "Mozilla/5.0 (LottoBot/1.0)"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Parse the first open draw
        if not data: return None
        draw = data[0]
        
        # Extract Jackpot (Safe method)
        # Note: Veikkaus returns cents. 1600000000 = 16M
        jackpot_cents = 0
        if 'jackpots' in draw and len(draw['jackpots']) > 0:
            jackpot_cents = draw['jackpots'][0]['amount']
            
        # Extract Price
        price_cents = draw['gameRuleSet']['basePrice']
        
        # Extract Time
        draw_time = draw['drawTime']
        draw_date_str = datetime.fromtimestamp(draw_time / 1000).strftime('%Y-%m-%d %H:%M')
        
        return {
            "name": NAMES[game_id],
            "jackpot": jackpot_cents / 100,
            "price": price_cents / 100,
            "next_draw": draw_date_str,
            "odds_jackpot": ODDS_CONFIG[game_id],
            "base_rtp": RTP_CONFIG[game_id],
            "currency": "€"
        }
        
    except Exception as e:
        print(f"Error fetching {game_id}: {e}")
        return None

def fetch_international_data():
    results = []

    headers = {
        "User-Agent": "Mozilla/5.0 (LottoBot/1.0)",
        "Accept": "application/json"
    }

    # 1. US POWERBALL (Source: NY State Gov API)
    pb_url = "https://data.ny.gov/resource/d6yy-54nr.json?$order=draw_date DESC&$limit=1"
    pb_est_url = "https://www.powerball.com/api/v1/estimates/powerball"

    # 2. MEGA MILLIONS (Source: NY State Gov API)
    mm_url = "https://data.ny.gov/resource/5xaw-6ayf.json?$order=draw_date DESC&$limit=1"
    mm_est_url = "https://www.megamillions.com/"

    # 3. EURO MILLIONS (Third-party API)
    em_url = "https://euromillions.api.pedromealha.dev/v1/draws?limit=1"

    try:
        # --- FETCH POWERBALL ---
        pb_data = _first_list_item(_safe_get(pb_url, headers=headers))
        if not pb_data:
            raise ValueError("No Powerball data returned")
        jackpot = (
            _parse_money(pb_data.get("jackpot")) or
            _parse_money(pb_data.get("estimated_jackpot")) or
            _parse_money(pb_data.get("jackpot_amount"))
        )
        if jackpot is None:
            pb_text = _safe_get(pb_est_url, headers=headers, expect_json=False)
            jackpot = _extract_jackpot_from_text(pb_text)
        if jackpot is None:
            raise ValueError("No Powerball jackpot from NY data or Powerball.com")

        results.append({
            "name": NAMES["POWERBALL"],
            "jackpot": jackpot,
            "price": 2.00,
            "next_draw": pb_data.get("draw_date"),
            "odds_jackpot": ODDS_CONFIG["POWERBALL"],
            "base_rtp": RTP_CONFIG["POWERBALL"],
            "currency": "$"
        })
    except Exception as e:
        print(f"Error fetching POWERBALL: {e}")

    try:
        # --- FETCH MEGA MILLIONS ---
        mm_data = _first_list_item(_safe_get(mm_url, headers=headers))
        if not mm_data:
            raise ValueError("No Mega Millions data returned")
        jackpot = (
            _parse_money(mm_data.get("jackpot")) or
            _parse_money(mm_data.get("estimated_jackpot")) or
            _parse_money(mm_data.get("jackpot_amount"))
        )
        if jackpot is None:
            mm_text = _safe_get(mm_est_url, headers=headers, expect_json=False)
            jackpot = _extract_jackpot_from_text(mm_text)
        if jackpot is None:
            raise ValueError("No Mega Millions jackpot from NY data or MegaMillions.com")

        results.append({
            "name": NAMES["MEGAMILLIONS"],
            "jackpot": jackpot,
            "price": 2.00,
            "next_draw": mm_data.get("draw_date"),
            "odds_jackpot": ODDS_CONFIG["MEGAMILLIONS"],
            "base_rtp": RTP_CONFIG["MEGAMILLIONS"],
            "currency": "$"
        })
    except Exception as e:
        print(f"Error fetching MEGAMILLIONS: {e}")

    try:
        # --- FETCH EUROMILLIONS ---
        em_data = _safe_get(em_url, headers=headers)
        em_draw = _first_list_item(em_data) or em_data
        jackpot = (
            _parse_money(em_draw.get("jackpot")) or
            _parse_money(em_draw.get("jackpot_amount")) or
            _parse_money(em_draw.get("jackpot_eur")) or
            _parse_money(em_draw.get("jackpotEur"))
        )
        next_draw = (
            em_draw.get("next_draw") or
            em_draw.get("nextDraw") or
            em_draw.get("next_draw_date") or
            em_draw.get("nextDrawDate") or
            em_draw.get("draw_date") or
            em_draw.get("drawDate") or
            em_draw.get("date")
        )

        if jackpot is not None:
            results.append({
                "name": NAMES["EUROMILLIONS"],
                "jackpot": jackpot,
                "price": em_draw.get("ticket_price") or em_draw.get("ticketPrice") or 2.50,
                "next_draw": next_draw,
                "odds_jackpot": ODDS_CONFIG["EUROMILLIONS"],
                "base_rtp": RTP_CONFIG["EUROMILLIONS"],
                "currency": "€"
            })
    except Exception as e:
        print(f"Error fetching EUROMILLIONS: {e}")

    return results

def update_database():
    results = []
    print("--- Starting Update Job ---")
    
    for game_id in ["LOTTO", "VIKING", "EJACKPOT"]:
        print(f"Fetching {game_id}...")
        data = fetch_game_data(game_id)
        if data:
            results.append(data)
            print(f"✅ Success: {data['name']} (€{data['jackpot']:,.0f})")
        else:
            print(f"❌ Failed to fetch {game_id}")
            
        time.sleep(1) # Be polite to the API

    print("Fetching international benchmarks...")
    results.extend(fetch_international_data())
        
    # Save to JSON
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "games": results
    }
    
    with open("lottery_data.json", "w", encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print("\n💾 Database updated: lottery_data.json")

if __name__ == "__main__":
    update_database()