from __future__ import annotations

import requests


def sanitize_city_name(city: str) -> str:
    first_part = city.split(",")[0]
    city_name = first_part.split("-")[0].strip()
    return city_name.replace(" ", "_")


def get_autocomplete_suggestions(query: str, limit: int = 5) -> list[str]:
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": limit}
    response = requests.get(base_url, params=params, timeout=20)
    if response.status_code != 200:
        return []
    data = response.json()
    return [place["display_name"] for place in data]
