import re
from typing import Tuple, List

# Configuration lists for normalization
FRANCHISE_PREFIXES = [
    r"\bSuper OYO Capital O\b",
    r"\bSuper OYO Townhouse\b",
    r"\bSuper OYO Collection O\b",
    r"\bSuper OYO Flagship\b",
    r"\bSuper OYO\b",
    r"\bCapital O\b",
    r"\bCollection O\b",
    r"\bTownhouse OAK\b",
    r"\bOYO Townhouse\b",
    r"\bOYO Rooms\b",
    r"\bSpot On\b",
    r"\bSPOT ON\b",
    r"\bSilverKey\b",
    r"\bPalette\b",
    r"\bOYO Home\b",
    r"\bOYO Flagship\b",
    r"\bOYO\b",
    r"\bFabHotel\b"
]

ROOM_PATTERN = r"\b\d{3,6}\b" # Identifies obvious numeric sequence like 604, 8501, 23641, 805147
PROMO_PATTERNS = [
    r"\bnear\s+d[\s\-]*mart\b",
    r"\bbest\s+hotel\b",
    r"\bbudget\s+hotel\b",
    r"\bcouple\s+friendly\b"
]

def clean_promotional_text(name: str, steps: list) -> str:
    current = name
    for promo in PROMO_PATTERNS:
        pattern = re.compile(promo, flags=re.IGNORECASE)
        if pattern.search(current):
            current = pattern.sub("", current).strip()
            steps.append(f"removed promotional text: {promo}")
    
    # Handle "Near [Location]" - just remove the word "Near " if it starts a trailing phrase
    # Or generically just remove the word "Near" if it's acting as a preposition, to keep the landmark.
    # The requirement says "remove or normalize... but preserve location". 
    # Example: "Near Inderlok Metro Station" -> "Inderlok Metro Station"
    near_match = re.search(r"\bnear\s+(.+)", current, flags=re.IGNORECASE)
    if near_match:
        landmark = near_match.group(1)
        current = re.sub(r"\bnear\s+", "", current, flags=re.IGNORECASE).strip()
        steps.append(f"preserved landmark but removed 'near': {landmark}")
        
    return current

def normalize_hotel_query(original_name: str) -> Tuple[str, List[str]]:
    """
    Takes an original hotel name and creates a normalized search representation.
    Returns structurally cleaned name, and list of transformation steps.
    """
    steps = []
    
    current_name = original_name
    
    # 1. Remove Franchise Prefixes
    for prefix in FRANCHISE_PREFIXES:
        pattern = re.compile(prefix, flags=re.IGNORECASE)
        if pattern.search(current_name):
            current_name = pattern.sub("", current_name).strip()
            # formatting nicely
            clean_prefix = prefix.replace(r"\b", "").strip()
            steps.append(f"removed franchise prefix: {clean_prefix}")
            break # typically only one main branding structure matters
            
    # 2. Remove Room/Booking Identifiers
    room_matches = re.findall(ROOM_PATTERN, current_name)
    if room_matches:
        for match in room_matches:
            current_name = re.sub(rf"\b{match}\b", "", current_name).strip()
            steps.append(f"removed numeric room/booking metadata: {match}")
            
    # 3. Promotional/SEO Text
    current_name = clean_promotional_text(current_name, steps)

    # 4. Punctuation and Formatting
    # Remove hyphens surrounded by spaces, non-alphanumeric (excluding space)
    clean_name = re.sub(r'[-\(\)\[\]]', ' ', current_name)
    clean_name = re.sub(r'[^\w\s]', '', clean_name)
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    
    if clean_name != current_name:
        steps.append("normalized punctuation and whitespace")
        current_name = clean_name

    # Check if empty
    if not current_name:
        return original_name, ["failed to normalize: string became empty, reverted"]
        
    return current_name, steps
