import requests
import json
import time
from datetime import datetime

# CONFIGURATION
# Base RTP estimates (Non-jackpot return to player)
RTP_CONFIG = {
    "LOTTO": 0.23,   # Finnish Lotto
    "VIKING": 0.25,  # Vikinglotto
    "EJACKPOT": 0.32 # Eurojackpot
}

ODDS_CONFIG = {
    "LOTTO": 18643560,
    "VIKING": 61357560,
    "EJACKPOT": 139838160
}

NAMES = {
    "LOTTO": "Finnish Lotto",
    "VIKING": "Vikinglotto",
    "EJACKPOT": "Eurojackpot"
}

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