## What it does
Scrapes all Pokémon card sets from pokellector.com. Saves each set as separate JSON file.

## How to use

```bash
# Install requirements
pip install requests beautifulsoup4

# Scrape 20 sets (test)
python scrapertest.py 20

# Scrape all sets
python scrapertest.py
```

## Output structure

```
pokemon_collection/
├── series_index.json          # Master list of all series
├── Base Set Series/
│   ├── Base Set.json          # Individual set file
│   ├── Base Set 2.json
│   └── ...
└── Sword & Shield Series/
    └── ...
```

## Key features

- **Incremental scraping** - Stops and resumes without repeating
- **Saves as you go** - Each set saved after scraping
- **Skips existing** - Won't re-scrape complete sets
- **Respectful delays** - Small pauses between requests
- **Error handling** - Keeps going even if one set fails

## Each set file contains

- Set metadata (link, logo, symbol)
- All cards with details
- Card images (thumb + full)
- Prices from TCG Player, eBay, Troll & Toad
- Alternate versions

## To assemble all into one file

Uncomment last line:
```python
# master = scraper.assemble_all_data()
```
