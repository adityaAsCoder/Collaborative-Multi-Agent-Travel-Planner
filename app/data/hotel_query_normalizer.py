import re

class HotelQueryNormalizer:
    
    PLATFORM_PREFIXES = [
        "OYO Rooms", "Super OYO", "Capital O", "Collection O", "Townhouse OAK", "Townhouse",
        "Spot On", "SilverKey", "Palette", "Home", "FabHotel", "OYO", "Flagship"
    ]
    
    PROMOTIONAL_PHRASES = [
        "near d mart", "couple friendly", "budget hotel", "best hotel", 
        "cheap hotel", "family hotel", "hotel near", "near metro station", "near airport",
        "near railway station", "near bus stand", "near metro", "near"
    ]

    def __init__(self):
        pass

    def normalize(self, original_name: str):
        steps = []
        name = original_name
        
        # 1. Platform & Franchise prefixes
        # Sort prefixes by length descending so "Super OYO" is matched before "OYO"
        prefixes = sorted(self.PLATFORM_PREFIXES, key=len, reverse=True)
        for prefix in prefixes:
            pattern = re.compile(rf'\b{re.escape(prefix)}\b', re.IGNORECASE)
            if pattern.search(name):
                temp_name = pattern.sub('', name)
                if temp_name.strip():
                    name = temp_name
                    steps.append(f"removed platform/franchise prefix: {prefix}")
                
        # 2. Room/booking metadata
        # Remove standalone numbers or "Room \d+"
        number_pattern = re.compile(r'\b\d+\b(?![\w-])', re.IGNORECASE)
        # e.g., "604" in "OYO Rooms 604"
        if number_pattern.search(name):
            temp_name = number_pattern.sub('', name)
            if temp_name.strip():
                name = temp_name
                steps.append("removed numeric room/booking metadata")
            
        # 3. Promotional/SEO text
        # Specifically targeting things like "Near D Mart" or "Near Metro Station"
        promo_pattern1 = re.compile(r'(?i)\bnear d mart\b', re.IGNORECASE)
        if promo_pattern1.search(name):
            temp_name = promo_pattern1.sub('', name)
            if temp_name.strip():
                name = temp_name
                steps.append("removed promotional location phrase: Near D Mart")
            
        promo_pattern2 = re.compile(r'(?i)\bnear [a-z\s]+ metro station\b', re.IGNORECASE)
        if promo_pattern2.search(name):
            temp_name = promo_pattern2.sub('', name)
            if temp_name.strip():
                name = temp_name
                steps.append("removed promotional location phrase: near metro station")
            
        generic_promo = re.compile(r'(?i)\b(couple friendly|budget hotel|best hotel)\b', re.IGNORECASE)
        if generic_promo.search(name):
            temp_name = generic_promo.sub('', name)
            if temp_name.strip():
                name = temp_name
                steps.append("removed promotional text")

        # 4. Punctuation and formatting
        # Replace hyphens with spaces
        if '-' in name:
            name = name.replace('-', ' ')
            steps.append("normalized punctuation: hyphens to spaces")
        
        # Remove extra whitespace and trim
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Title case for cleanliness
        name = name.title()

        return name, steps

    def extract_locality(self, address: str) -> str:
        if not address:
            return ""
        parts = [p.strip() for p in address.split(",")]
        if len(parts) > 1:
            return parts[0]
        return ""

    def generate_queries(self, normalized_name: str, original_city: str, original_address: str):
        queries = []
        city = original_city.strip() if original_city else ""
        address = original_address.strip() if original_address else ""
        
        # Query 1: <normalized hotel name> + <city>
        if city:
            q1 = f"{normalized_name} {city}".strip()
            if q1:
                queries.append(q1)
        else:
            q1 = f"{normalized_name}".strip()
            if q1:
                queries.append(q1)
                
        # Query 2: <normalized hotel name> + <locality> + <city>
        locality = self.extract_locality(address)
        if locality and locality.lower() not in city.lower():
            q2 = f"{normalized_name} {locality} {city}".strip()
            # To avoid duplicates if locality is already in query 1
            if q2 not in queries:
                queries.append(q2)
                
        # Query 3: <normalized hotel name> + <address/location> + <city>
        if address:
            # Clean address to remove city if it's appended at the end
            clean_addr = address
            if city and clean_addr.endswith(city):
                clean_addr = clean_addr[:len(clean_addr)-len(city)].strip().rstrip(',')
                
            q3 = f"{normalized_name} {clean_addr} {city}".strip()
            # We don't want to create massive queries if the address is too long, but we'll try it
            q3_clean = re.sub(r'\s+', ' ', q3).strip()
            if q3_clean not in queries:
                queries.append(q3_clean)
                
        return queries
