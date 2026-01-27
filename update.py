import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
RTP_CONFIG = {
    "LOTTO": 0.23, "VIKING": 0.25, "EJACKPOT": 0.32,
    "POWERBALL": 0.15, "MEGAMILLIONS": 0.15, "EUROMILLIONS": 0.20,
    "SUPERENALOTTO": 0.60
}

ODDS_CONFIG = {
    "LOTTO": 18643560, "VIKING": 61357560, "EJACKPOT": 139838160,
    "POWERBALL": 292201338, "MEGAMILLIONS": 302575350, "EUROMILLIONS": 139838160,
    "SUPERENALOTTO": 622614630
}

NAMES = {
    "LOTTO": "Finnish Lotto",
    "VIKING": "Vikinglotto",
    "EJACKPOT": "Eurojackpot",
    "POWERBALL": "US Powerball",
    "MEGAMILLIONS": "Mega Millions",
    "EUROMILLIONS": "EuroMillions",
    "SUPERENALOTTO": "SuperEnalotto"
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# --- HELPERS ---
def _next_weekday_date(weekday_name):
    try:
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
        }
        target = weekdays.get(weekday_name.lower())
        if target is None:
            return None
        today = datetime.now().date()
        delta = (target - today.weekday()) % 7
        if delta == 0:
            delta = 7
        return (today + timedelta(days=delta)).strftime("%Y-%m-%d")
    except Exception:
        return None

def _next_multi_weekday_date(weekday_indices):
    try:
        today = datetime.now().date()
        candidates = []
        for target in weekday_indices:
            delta = (target - today.weekday()) % 7
            if delta == 0:
                delta = 7
            candidates.append(today + timedelta(days=delta))
        return min(candidates).strftime("%Y-%m-%d")
    except Exception:
        return None

def _next_euromillions_draw_date():
    # EuroMillions draws on Tuesdays and Fridays
    try:
        return _next_multi_weekday_date([1, 4])
    except Exception:
        return None

def _next_superenalotto_draw_date():
    # SuperEnalotto draws on Tue/Thu/Fri/Sat
    try:
        return _next_multi_weekday_date([1, 3, 4, 5])
    except Exception:
        return None

# --- 1. VEIKKAUS ---
def fetch_veikkaus(game_id):
    url = f"https://www.veikkaus.fi/api/draw-open-games/v1/games/{game_id}/draws"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        if resp.status_code != 200: return None
        data = resp.json()
        if not data: return None
        
        draw = data[0]
        return {
            "name": NAMES[game_id],
            "jackpot": draw['jackpots'][0]['amount'] / 100,
            "price": draw['gameRuleSet']['basePrice'] / 100,
            "next_draw": datetime.fromtimestamp(draw['drawTime'] / 1000).strftime('%Y-%m-%d'),
            "currency": "€",
            "odds_jackpot": ODDS_CONFIG[game_id],
            "base_rtp": RTP_CONFIG[game_id]
        }
    except Exception as e:
        print(f"⚠️ Veikkaus {game_id} Error: {e}")
        return None

# --- 2. US SCRAPER (Fixed for Newlines) ---
def scrape_lotteryusa(game_key, url):
    print(f"   Scraping {NAMES[game_key]} from LotteryUSA...")
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        jackpot_val = 0
        date_str = "Check Site"
        
        # Iterate over ALL title boxes to find the matching ones
        # This ignores the "Next \n Powerball \n draw" spacing issues
        titles = soup.find_all(class_="c-state-short-info__title")
        
        for title_box in titles:
            text = title_box.get_text(" ", strip=True).lower() # "next powerball draw"
            
            # --- A. FIND DATE ---
            # Check if this box is the "Next Draw" label
            target_name = "powerball" if game_key == "POWERBALL" else "mega millions"
            
            if "next" in text and target_name in text and "draw" in text:
                # The date is in the sibling <time> tag
                time_tag = title_box.find_next_sibling("time")
                if time_tag:
                    date_text = time_tag.get_text(strip=True) # "Today at 10:59 pm EST"
                    
                    if "Today" in date_text:
                        date_str = datetime.now().strftime('%Y-%m-%d')
                    elif "Tomorrow" in date_text:
                        date_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                    else:
                        # Look for "Jan 24"
                        match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})', date_text, re.IGNORECASE)
                        if match:
                            month_str = match.group(1)
                            day_str = match.group(2)
                            try:
                                year = datetime.now().year
                                dt = datetime.strptime(f"{month_str} {day_str} {year}", "%b %d %Y")
                                if dt < datetime.now() - timedelta(days=60): dt = dt.replace(year=year + 1)
                                date_str = dt.strftime('%Y-%m-%d')
                            except:
                                pass

            # --- B. FIND JACKPOT ---
            if "next" in text and "est" in text and "jackpot" in text:
                # Valid jackpot box. Now we must ensure it's for the RIGHT game.
                # Usually, LotteryUSA pages only show ONE game's jackpot per URL.
                # So any "Next est. jackpot" on the page is safe to take.
                
                subtitle_div = title_box.find_next_sibling(class_="c-state-short-info__subtitle")
                if subtitle_div:
                    # Destroy the "Cash value" span to avoid confusion
                    for span in subtitle_div.find_all('span'):
                        span.decompose()
                    
                    money_text = subtitle_div.get_text(strip=True)
                    match = re.search(r'\$\s?([0-9.]+)\s?(Million|Billion)', money_text, re.IGNORECASE)
                    if match:
                        val = float(match.group(1))
                        if "billion" in match.group(2).lower(): val *= 1_000_000_000
                        else: val *= 1_000_000
                        jackpot_val = val

        if jackpot_val > 0:
            return {
                "name": NAMES[game_key],
                "jackpot": jackpot_val,
                "price": 2.00,
                "next_draw": date_str,
                "currency": "$",
                "odds_jackpot": ODDS_CONFIG[game_key],
                "base_rtp": RTP_CONFIG[game_key]
            }
        else:
            print(f"❌ '{NAMES[game_key]}' Jackpot not found.")
            return None

    except Exception as e:
        print(f"⚠️ Scrape Error {game_key}: {e}")
        return None

# --- 3. EUROMILLIONS ---
def scrape_euromillions():
    print(f"   Scraping EuroMillions from Lottery.ie...")
    url = "https://www.lottery.ie/draw-games/euromillions"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        jackpot_val = 0
        date_str = "Check Site"
        
        # 1. FIND JACKPOT
        # Irish site usually has a clear "Jackpot" h1 block
        full_text = soup.get_text(separator=" ", strip=True)
        
        # A) Prefer "€110 Million Jackpot" from the hero title
        for h1 in soup.find_all("h1"):
            h1_text = h1.get_text(" ", strip=True)
            if "€" in h1_text and "jackpot" in h1_text.lower():
                match = re.search(r'€\s?([0-9,]+(\.[0-9]+)?)\s?(Million)?', h1_text, re.IGNORECASE)
                if match:
                    amount_str = match.group(1).replace(",", "")
                    try:
                        val = float(amount_str)
                        if match.group(3) and "million" in match.group(3).lower():
                            val *= 1_000_000
                        if val > 15_000_000: # EuroMillions min jackpot is 17M, so ignore small prizes
                            jackpot_val = val
                            break
                    except:
                        pass
        
        # B) Fallback: scan entire page for largest Euro value
        if jackpot_val == 0:
            # Regex to find: €17,000,000 or €130 Million
            # It scans the whole page for the biggest Euro value (Jackpot is always biggest)
            matches = re.findall(r'€\s?([0-9,]+(\.[0-9]+)?)\s?(Million)?', full_text, re.IGNORECASE)
            
            candidates = []
            for m in matches:
                amount_str = m[0].replace(",", "")
                try:
                    val = float(amount_str)
                    if m[2] and "million" in m[2].lower():
                        val *= 1_000_000
                    if val > 15_000_000: # EuroMillions min jackpot is 17M, so ignore small prizes
                        candidates.append(val)
                except:
                    continue
                    
            if candidates:
                jackpot_val = max(candidates) # Assume biggest number is the jackpot

        # 2. FIND DATE
        # A) Pattern like "Next Draw: Friday, 30th January"
        draw_match = re.search(r'Next Draw:?\s+([A-Za-z]+,?\s+\d{1,2}(st|nd|rd|th)?\s+[A-Za-z]+)', full_text, re.IGNORECASE)
        if draw_match:
            # Matches: "Friday, 30th January"
            date_text = draw_match.group(1)
            # Clean "30th" -> "30"
            clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_text)
            
            match = re.search(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', clean_date, re.IGNORECASE)
            if match:
                try:
                    year = datetime.now().year
                    dt = datetime.strptime(f"{match.group(1)} {match.group(2)} {year}", "%d %b %Y")
                    if dt < datetime.now() - timedelta(days=60):
                        dt = dt.replace(year=year + 1)
                    date_str = dt.strftime('%Y-%m-%d')
                except:
                    pass
        # B) Pattern like "Tomorrow, 7:30pm" or "Tuesday, 7:30pm"
        if date_str == "Check Site":
            # Match visible "Today/Tomorrow, 7:30pm" style strings
            relative_time = re.search(
                r'(Today|Tomorrow)\s*,?\s*\d{1,2}:\d{2}\s*(am|pm)?',
                full_text,
                re.IGNORECASE
            )
            if relative_time:
                if relative_time.group(1).lower() == "today":
                    date_str = datetime.now().strftime('%Y-%m-%d')
                else:
                    date_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                # Match visible "Tuesday, 7:30pm" style strings
                weekday_time = re.search(
                    r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*,?\s*\d{1,2}:\d{2}\s*(am|pm)?',
                    full_text,
                    re.IGNORECASE
                )
                if weekday_time:
                    next_date = _next_weekday_date(weekday_time.group(1))
                    if next_date:
                        date_str = next_date
                else:
                    # Fallback: search specifically in <p> tags for the weekday/time snippet
                    for p in soup.find_all("p"):
                        p_text = p.get_text(" ", strip=True)
                        p_match = re.search(
                            r'(Today|Tomorrow|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*,?\s*\d{1,2}:\d{2}\s*(am|pm)?',
                            p_text,
                            re.IGNORECASE
                        )
                        if p_match:
                            token = p_match.group(1).lower()
                            if token == "today":
                                date_str = datetime.now().strftime('%Y-%m-%d')
                            elif token == "tomorrow":
                                date_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                            else:
                                next_date = _next_weekday_date(p_match.group(1))
                                if next_date:
                                    date_str = next_date
                            if date_str != "Check Site":
                                break

        if date_str == "Check Site":
            print("⚠️ EuroMillions date not found in page text.")
            fallback_date = _next_euromillions_draw_date()
            if fallback_date:
                date_str = fallback_date

        if jackpot_val > 0:
            return {
                "name": NAMES["EUROMILLIONS"],
                "jackpot": jackpot_val,
                "price": 2.50,
                "next_draw": date_str,
                "currency": "€",
                "odds_jackpot": ODDS_CONFIG["EUROMILLIONS"],
                "base_rtp": RTP_CONFIG["EUROMILLIONS"]
            }
        
        print("❌ EuroMillions: Could not find jackpot pattern.")
        return None

    except Exception as e:
        print(f"⚠️ EuroMillions Error: {e}")
        return None

# --- 4. SUPERENALOTTO ---
def scrape_superenalotto():
    print("   Scraping SuperEnalotto from superenalotto.net...")
    url = "https://www.superenalotto.net/en"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

        jackpot_val = 0
        date_str = "Check Site"

        full_text = soup.get_text(separator=" ", strip=True)

        # 1. FIND JACKPOT
        jackpot_match = re.search(
            r'Estimated Jackpot\s+€\s?([0-9,.]+)\s*(Million|Billion)?',
            full_text,
            re.IGNORECASE
        )
        if jackpot_match:
            amount_str = jackpot_match.group(1).replace(",", "")
            try:
                val = float(amount_str)
                if jackpot_match.group(2):
                    unit = jackpot_match.group(2).lower()
                    if "billion" in unit:
                        val *= 1_000_000_000
                    elif "million" in unit:
                        val *= 1_000_000
                jackpot_val = val
            except:
                pass

        if jackpot_val == 0:
            matches = re.findall(r'€\s?([0-9,]+(\.[0-9]+)?)\s*(Million|Billion)?', full_text, re.IGNORECASE)
            candidates = []
            for m in matches:
                amount_str = m[0].replace(",", "")
                try:
                    val = float(amount_str)
                    if m[2]:
                        unit = m[2].lower()
                        if "billion" in unit:
                            val *= 1_000_000_000
                        elif "million" in unit:
                            val *= 1_000_000
                    if val >= 2_000_000:
                        candidates.append(val)
                except:
                    continue
            if candidates:
                jackpot_val = max(candidates)

        # 2. FIND DATE (fallback to schedule)
        if date_str == "Check Site":
            fallback_date = _next_superenalotto_draw_date()
            if fallback_date:
                date_str = fallback_date

        if jackpot_val > 0:
            return {
                "name": NAMES["SUPERENALOTTO"],
                "jackpot": jackpot_val,
                "price": 1.00,
                "next_draw": date_str,
                "currency": "€",
                "odds_jackpot": ODDS_CONFIG["SUPERENALOTTO"],
                "base_rtp": RTP_CONFIG["SUPERENALOTTO"]
            }

        print("❌ SuperEnalotto: Could not find jackpot pattern.")
        return None

    except Exception as e:
        print(f"⚠️ SuperEnalotto Error: {e}")
        return None

    except Exception as e:
        print(f"⚠️ EuroMillions Error: {e}")
        return None

# --- MAIN RUNNER ---
def update_database():
    games_list = []
    print("--- Starting Update Job ---")
    
    # 1. VEIKKAUS
    for gid in ["LOTTO", "VIKING", "EJACKPOT"]:
        g = fetch_veikkaus(gid)
        if g: games_list.append(g); print(f"✅ Success: {g['name']}")

    # 2. US GAMES
    pb = scrape_lotteryusa("POWERBALL", "https://www.lotteryusa.com/powerball/")
    if pb: games_list.append(pb); print(f"✅ Success: US Powerball ({pb['jackpot']} - {pb['next_draw']})")
    
    mm = scrape_lotteryusa("MEGAMILLIONS", "https://www.lotteryusa.com/mega-millions/")
    if mm: games_list.append(mm); print(f"✅ Success: Mega Millions ({mm['jackpot']} - {mm['next_draw']})")

    # 3. EUROMILLIONS
    em = scrape_euromillions()
    if em: games_list.append(em); print(f"✅ Success: EuroMillions ({em['jackpot']} - {em['next_draw']})")

    # 4. SUPERENALOTTO
    se = scrape_superenalotto()
    if se: games_list.append(se); print(f"✅ Success: SuperEnalotto ({se['jackpot']} - {se['next_draw']})")

    # SAVE
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "games": games_list
    }
    
    with open("lottery_data.json", "w", encoding='utf-8') as f:
        json.dump(output, f, indent=2)
        
    print("\n💾 Database saved.")

if __name__ == "__main__":
    update_database()