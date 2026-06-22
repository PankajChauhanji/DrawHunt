import json
import random
import os
from typing import List, Optional, Dict, Any

def load_word_bank(filepath: str = "words.json") -> List[Dict[str, Any]]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, filepath)
    
    valid_words = []
    required_keys = {"word", "lang", "themes"}
    
    try:
        with open(full_path, 'r', encoding='utf-8') as file:
            raw_data = json.load(file)
            
        # Validate each entry before adding it to our active pool
        for entry in raw_data:
            # Check if it's a dictionary and has all required keys
            if isinstance(entry, dict) and required_keys.issubset(entry.keys()):
                valid_words.append(entry)
            else:
                # You can log this to a file in production, or just print it for debugging
                print(f"Skipping malformed entry: {entry}")
                
        return valid_words
        
    except FileNotFoundError:
        print(f"Warning: {filepath} not found. Returning empty word bank.")
        return []

# Initialize the global word bank
WORD_BANK = load_word_bank()

# ... (pick_random_words and pick_words_with_metadata functions remain exactly the same)

WORD_BANK = load_word_bank()

def pick_choices(n: int, exclude: Optional[set[str]] = None) -> List[str]:
    exclude = exclude or set()
    
    # Using dictionary syntax: entry["word"]
    pool = [entry["word"] for entry in WORD_BANK if entry["word"] not in exclude]
    
    if len(pool) < n:               
        pool = [entry["word"] for entry in WORD_BANK]
        
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
        
    # We no longer need asdict(), we just return the sampled dictionaries directly!
    return random.sample(pool, min(n, len(pool)))