"""Deterministic interest matching shared by itinerary and catalog views."""

from __future__ import annotations

import re
from typing import Any


INTEREST_TERMS = {
    "history": {"history", "historic", "historical", "heritage", "fort", "fortress", "palace", "monument", "archaeology", "archaeological", "museum", "ancient"},
    "forts": {"fort", "forts", "fortress", "castle", "citadel"},
    "culture": {"culture", "cultural", "heritage", "tradition", "traditional", "art", "arts", "festival", "craft"},
    "food": {"food", "cuisine", "culinary", "restaurant", "market", "street"},
    "nature": {"nature", "natural", "lake", "beach", "waterfall", "river", "wildlife", "forest", "garden", "sanctuary", "bird", "valley", "island"},
    "religious": {"religious", "spiritual", "temple", "shrine", "church", "monastery", "mosque", "stupa", "ghat", "hindu", "buddhist", "christian", "sikh"},
    "adventure": {"adventure", "trek", "trekking", "rafting", "cruise", "cruises", "houseboat", "safari", "camping"},
    "beach": {"beach", "beaches", "coast", "shore", "seaside"},
}

PLURAL_NORMALIZATION = {
    "forts": "fort",
    "cruises": "cruise",
    "beaches": "beach",
    "temples": "temple",
    "lakes": "lake",
    "sanctuaries": "sanctuary",
    "museums": "museum",
}


def matched_interests(attraction: dict[str, Any], interests: list[str]) -> list[str]:
    text = " ".join(
        str(attraction.get(field) or "")
        for field in ("name", "category", "subcategory", "description")
    )
    words = {
        PLURAL_NORMALIZATION.get(word, word)
        for word in re.findall(r"[a-z0-9]+", text.casefold())
    }
    matches = []
    for interest in interests:
        key = re.sub(r"[^a-z0-9]+", "", str(interest).casefold())
        terms = INTEREST_TERMS.get(key, {PLURAL_NORMALIZATION.get(key, key)})
        normalized_terms = {PLURAL_NORMALIZATION.get(term, term) for term in terms}
        if words.intersection(normalized_terms):
            matches.append(str(interest))
    return matches
