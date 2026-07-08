import requests
import json
import sys
import time
import re
import os
from bs4 import BeautifulSoup

class PokemonSetScraper:
    def __init__(self, base_url, output_dir="pokemon_data"):
        self.series_list = []
        self.base_url = base_url
        self.cards = []
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

    def safe_request(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                return resp
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                print(f"Request failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        return None

    def stage_1(self, base_url="https://pokellector.com/sets"):
        """Get all series and sets, save series index"""
        resp = self.safe_request(base_url)
        if not resp:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        series_set_dict = {}
        seterrors = 0
        serieserror = 0

        for h1 in soup.find_all("h1", class_="icon set"):
            series_name = h1.get_text(strip=True)
            series_img = h1.find("img")["src"] if h1.find("img") else None
            print(f"Parsing Series: [----{series_name}----]")
            time.sleep(0.05)

            sets_div = h1.find_next_sibling("div", class_="content buttonlisting english")
            sets = {}

            if sets_div:
                for a in sets_div.find_all("a", class_="button"):
                    set_name = a.find("span").get_text(strip=True) if a.find("span") else None

                    if set_name:
                        print(f"  Parsing SET: [----{set_name}----]")
                    else:
                        seterrors += 1
                        print("  Parsing ERROR: no set found")

                    time.sleep(0.003)

                    set_title = a.get("title")
                    set_link = a.get("href")
                    imgs = a.find_all("img")
                    logo_img = imgs[0]["src"] if len(imgs) > 0 else None
                    symbol_img = imgs[1]["src"] if len(imgs) > 1 else None

                    sets[set_name] = {
                        "title": set_title,
                        "link": set_link,
                        "logo": logo_img,
                        "symbol": symbol_img,
                        "scraped": False  # Flag to track if scraped
                    }
            else:
                serieserror += 1
                print(f"Series ERROR: No sets found for {series_name}")

            series_set_dict[series_name] = {
                "image": series_img,
                "sets": sets
            }

        # Save series index
        self.save_series_index(series_set_dict)
        print(f"---seterrors: {seterrors}")
        print(f"---serieserrors: {serieserror}")
        return series_set_dict

    def save_series_index(self, series_dict):
        """Save master list of all series and sets"""
        index_path = os.path.join(self.output_dir, "series_index.json")
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(series_dict, f, indent=2, ensure_ascii=False)
        print(f"Series index saved to {index_path}")

    def scrape_set_cards(self, set_url):
        """Scrape cards from a set page"""
        if not set_url.startswith("https://"):
            set_url = "https://www.pokellector.com" + set_url

        resp = self.safe_request(set_url)
        if not resp:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        card_elements = soup.find_all("div", class_="card")
        cards = []

        for card in card_elements:
            plaque = card.find("div", class_="plaque")
            if plaque:
                plaque_text = plaque.get_text(strip=True)
                match = re.match(r'#(\d+)\s*-\s*(.+)', plaque_text)
                if match:
                    card_number = match.group(1)
                    card_name = match.group(2)
                else:
                    card_number = None
                    card_name = plaque_text
            else:
                card_number = None
                card_name = None

            link_tag = card.find("a")
            if link_tag:
                card_link = link_tag.get("href", "")
                card_title = link_tag.get("title", "")
            else:
                card_link = ""
                card_title = ""

            img_tag = card.find("img", class_="card")
            if img_tag:
                image_url = img_tag.get("data-src") or img_tag.get("src", "")
            else:
                image_url = ""

            cards.append({
                "number": card_number,
                "name": card_name,
                "title": card_title,
                "link": card_link,
                "image": image_url,
                "full_image": image_url.replace(".thumb.", ".") if image_url else "",
                "details_scraped": False  # Flag for stage_3
            })

        return cards

    def stage_3(self, card_url):
        """Scrape detailed card data"""
        if not card_url:
            return {}

        full_url = "https://pokellector.com" + card_url

        try:
            resp = self.safe_request(full_url)
            if not resp:
                return {"error": "Failed to fetch card page"}
        except Exception as e:
            return {"error": str(e)}

        soup = BeautifulSoup(resp.text, "html.parser")
        card_info = {}

        # Card name and number
        h1 = soup.find("h1", class_="icon set")
        if h1:
            for img in h1.find_all("img"):
                img.decompose()

            h1_text = h1.get_text(strip=True)
            if "#" in h1_text:
                parts = h1_text.split("#", 1)
                card_info["name"] = parts[0].strip()
                card_info["number"] = parts[1].strip()
            else:
                card_info["name"] = h1_text

        # Rarity, Set, Position
        infoblurb = soup.find("div", class_="infoblurb")
        if infoblurb:
            for div in infoblurb.find_all("div"):
                text = div.get_text(strip=True)
                if "Rarity:" in text:
                    card_info["rarity"] = text.replace("Rarity:", "").strip()
                elif "Set:" in text:
                    set_link = div.find("a")
                    if set_link:
                        card_info["set_name"] = set_link.get_text(strip=True)
                        card_info["set_link"] = set_link.get("href", "")
                elif "Card:" in text:
                    card_link = div.find("a")
                    if card_link:
                        card_pos = card_link.get_text(strip=True)
                        card_info["position"] = card_pos
                        if "/" in card_pos:
                            current, total = card_pos.split("/")
                            card_info["card_number"] = current
                            card_info["total_cards"] = total

        # Full image
        card_div = soup.find("div", class_="card")
        card_img = card_div.find("img") if card_div else None
        if card_img:
            card_info["image_full"] = card_img.get("src", "")

        # Prices
        prices = []
        price_blurbs = soup.find_all("div", class_="priceblurb")
        for blur in price_blurbs:
            vendor_logo = blur.find("img")
            vendor_name = vendor_logo.get("src", "") if vendor_logo else ""

            if "TCG-Player" in vendor_name:
                vendor = "TCG Player"
            elif "Troll-Toad" in vendor_name:
                vendor = "Troll & Toad"
            elif "eBay" in vendor_name:
                vendor = "eBay"
            elif "Collectors-Cache" in vendor_name:
                vendor = "Collector's Cache"
            elif "CoolStuffInc" in vendor_name:
                vendor = "Cool Stuff Inc"
            else:
                vendor = "Unknown"

            price_div = blur.find("div", class_="price")
            price = price_div.get_text(strip=True) if price_div else ""

            link_tag = blur.find("a", class_="logo")
            link = link_tag.get("href", "") if link_tag else ""

            if price:
                prices.append({
                    "vendor": vendor,
                    "price": price,
                    "link": link
                })

        card_info["prices"] = prices

        # Alternate versions
        alternates = []
        alt_section = soup.find("a", {"name": "variants"})
        if alt_section:
            cardlisting = alt_section.find_next("div", class_="cardlisting")
            if cardlisting:
                for card_div in cardlisting.find_all("div", class_="card"):
                    alt_data = {}

                    plaque = card_div.find("div", class_="plaque")
                    if plaque:
                        alt_data["name"] = plaque.get_text(strip=True)

                    img_tag = card_div.find("img", class_="card")
                    if img_tag:
                        alt_data["image"] = img_tag.get("data-src") or img_tag.get("src", "")
                    else:
                        alt_data["image"] = None

                    link_tag = card_div.find("a")
                    if link_tag and link_tag.get("href") != "#":
                        alt_data["link"] = link_tag.get("href", "")
                        alt_data["title"] = link_tag.get("title", "")
                    else:
                        alt_data["link"] = None
                        alt_data["title"] = None

                    alternates.append(alt_data)

        card_info["alternate_versions"] = alternates
        card_info["details_scraped"] = True

        return card_info

    def save_set_data(self, series_name, set_name, set_data):
        """Save individual set to JSON file in series folder"""
        # Clean folder names (remove invalid chars)
        series_folder = re.sub(r'[<>:"/\\|?*]', '_', series_name)
        set_filename = re.sub(r'[<>:"/\\|?*]', '_', set_name) + ".json"

        series_path = os.path.join(self.output_dir, series_folder)
        os.makedirs(series_path, exist_ok=True)

        filepath = os.path.join(series_path, set_filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(set_data, f, indent=2, ensure_ascii=False)

        print(f"    Saved: {series_folder}/{set_filename}")
        return filepath

    def load_existing_set(self, series_name, set_name):
        """Check if set already scraped"""
        series_folder = re.sub(r'[<>:"/\\|?*]', '_', series_name)
        set_filename = re.sub(r'[<>:"/\\|?*]', '_', set_name) + ".json"

        filepath = os.path.join(self.output_dir, series_folder, set_filename)

        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def run_incremental(self, max_sets=None, skip_existing=True):
        """Scrape incrementally, saving each set as separate JSON"""
        print("Starting incremental scraping...")

        # Get series index
        stage1 = self.stage_1()

        total_sets = sum(len(series_data["sets"]) for series_data in stage1.values())
        print(f"Found {len(stage1)} series with {total_sets} total sets")

        if max_sets:
            print(f"Limiting to {max_sets} sets")

        set_count = 0
        scraped_count = 0

        for series_name, series_data in stage1.items():
            print(f"\n=== Series: {series_name} ===")

            for set_name, set_data in series_data["sets"].items():
                set_count += 1

                if max_sets and scraped_count >= max_sets:
                    print(f"Reached limit of {max_sets} sets. Stopping.")
                    return

                # Check if already scraped
                if skip_existing:
                    existing = self.load_existing_set(series_name, set_name)
                    if existing and existing.get("cards"):
                        print(f"  [{set_count}/{total_sets}] Skipping (already scraped): {set_name}")
                        continue

                print(f"  [{set_count}/{total_sets}] Scraping set: {set_name}")

                try:
                    # Get cards for this set
                    cards_list = self.scrape_set_cards(set_data["link"])

                    # Add cards to set data
                    set_data["cards"] = {}

                    # Process each card
                    for i, card in enumerate(cards_list):
                        if card.get("link") and not card.get("details_scraped", False):
                            print(f"    Card {i+1}/{len(cards_list)}: {card.get('name', 'Unknown')}")
                            card_details = self.stage_3(card["link"])
                            card.update(card_details)
                            time.sleep(0.3)  # Delay between card details

                        card_key = card.get("number") or card.get("name", f"unknown_{i}")
                        set_data["cards"][card_key] = card

                    # Mark as scraped
                    set_data["scraped"] = True
                    set_data["scraped_date"] = time.strftime("%Y-%m-%d %H:%M:%S")

                    # Save this set immediately
                    self.save_set_data(series_name, set_name, set_data)
                    scraped_count += 1

                    # Update series index
                    stage1[series_name]["sets"][set_name] = set_data
                    self.save_series_index(stage1)

                    # Delay between sets
                    print(f"    Waiting 3 seconds before next set...")
                    time.sleep(0.3)

                except Exception as e:
                    print(f"    ERROR processing set {set_name}: {e}")
                    # Save partial data if possible
                    set_data["error"] = str(e)
                    self.save_set_data(series_name, set_name, set_data)
                    continue

        print(f"\nScraping complete! Scraped {scraped_count} sets.")
        return stage1

    def assemble_all_data(self):
        """Combine all saved JSON files into one master file"""
        master_data = {}

        for series_folder in os.listdir(self.output_dir):
            series_path = os.path.join(self.output_dir, series_folder)

            if os.path.isdir(series_path):
                series_data = {
                    "sets": {}
                }

                # Check for series info in index
                index_path = os.path.join(self.output_dir, "series_index.json")
                if os.path.exists(index_path):
                    with open(index_path, "r", encoding="utf-8") as f:
                        index_data = json.load(f)
                        if series_folder in index_data:
                            series_data.update(index_data[series_folder])

                # Load all set files in this series
                for filename in os.listdir(series_path):
                    if filename.endswith(".json"):
                        set_name = filename[:-5]  # Remove .json
                        filepath = os.path.join(series_path, filename)

                        with open(filepath, "r", encoding="utf-8") as f:
                            set_data = json.load(f)

                        series_data["sets"][set_name] = set_data

                master_data[series_folder] = series_data

        # Save master file
        master_path = os.path.join(self.output_dir, "master_collection.json")
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)

        print(f"Assembled master file: {master_path}")
        return master_data

# Usage:
scraper = PokemonSetScraper("https://pokellector.com", output_dir="pokemon_collection")
max = 20
# Scrape a few sets first (for testing)
#scraper.run_incremental(max_sets=3, skip_existing=True)
if len(sys.argv) > 1:
    max = int(sys.argv[1])
# Later, resume scraping more
print(f"scraping {max} sets")
scraper.run_incremental(max_sets=max, skip_existing=True)

# When done, assemble everything
# master = scraper.assemble_all_data()



'''

#okay so the code would look like this  

binary = somebinary
#length = len(str(bin))

def parsing_logic_to_group_into_tuple(somebin): #we'll just call this as parse() for conciseness
        
    tuplelist = []

    counter1:int = 0
    counter2:int =  0
    countlist = []
    count = 0


    place
    listbin =list(str(bin))
    previous = ""
    assembly1 = 0
    assembly2 = 0
    4bitcounter = 0

    for i, x in enumerate(listbin):
        x = int(x)
        
        if counter1 == 0:
            counter1 = counter1 + 1

            countlist.append(x)
            assembly1 = x
            continue

            if not 4bitcounter >= 4: #4 bit processor
                4bitcounter += 1
                count += 1
                
            else: 
                4bitcounter = 0
                if x == '0': #flag
                    assembly2 = count
                    tuplelist.append((assembly1,assembly2))
                    continue
                else:
                    count += 1
        else: 
            counter1 = 0

tuplist= parsing_logic_to_group_into_tuple(somebinstr)

	
'''