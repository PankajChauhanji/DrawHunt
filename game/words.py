import json
import random
from pathlib import Path
from typing import List, Optional, Dict, Any
from config import Config

def load_word_bank() -> List[Dict[str, Any]]:
    # Resolve absolute path dynamically: root -> data -> json -> words.json
    PROJECT_ROOT = Path(__file__).parent.parent
    JSON_FILE_PATH = PROJECT_ROOT / "data" / "json" / Config.WORDS_FILE_NAME
    
    # --- AUTO-GENERATION LOGIC ---
    if not JSON_FILE_PATH.exists():
        print(f"Warning: {Config.WORDS_FILE_NAME} not found. Auto-generating...")
        # Import dynamically here to avoid circular imports on startup
        from game.words_generator import generate_json
        generate_json()
    
    valid_words = []
    required_keys = {"word", "lang", "themes"}
    
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as file:
            raw_data = json.load(file)
            
        # Validate each entry before adding it
        for entry in raw_data:
            if isinstance(entry, dict) and required_keys.issubset(entry.keys()):
                valid_words.append(entry)
            else:
                print(f"Skipping malformed entry: {entry}")
                
        return valid_words
        
    except Exception as e:
        print(f"CRITICAL WARNING: Failed to load word bank at {JSON_FILE_PATH}. Error: {e}")
        return []

# Initialize the global word bank
WORD_BANK = load_word_bank()

def pick_choices(n: int, exclude: Optional[set[str]] = None) -> List[str]:
    exclude = exclude or set()
    
    # Using dictionary syntax: entry["word"]
    pool = [entry["word"] for entry in WORD_BANK if entry["word"] not in exclude]
    
    if len(pool) < n:               
        pool = [entry["word"] for entry in WORD_BANK]
        
    # Return empty list safely if database is completely empty
    if not pool:
        return []
        
    return random.sample(pool, min(n, len(pool)))

def pick_choices_with_metadata(
    n: int, 
    exclude: Optional[set[str]] = None, 
    lang: Optional[str] = None, 
    theme: Optional[str] = None
) -> List[Dict[str, Any]]:
    exclude = exclude or set()
    
    pool = []
    for entry in WORD_BANK:
        if entry["word"] in exclude: continue
        if lang and entry["lang"] != lang: continue
        if theme and theme not in entry["themes"]: continue
        pool.append(entry)
        
    if len(pool) < n:
        pool = [
            e for e in WORD_BANK 
            if (not lang or e["lang"] == lang) and (not theme or theme in e["themes"])
        ]
        
    if not pool:
        return []
        
    return random.sample(pool, min(n, len(pool)))