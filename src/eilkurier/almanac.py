"""Weather (DWD via Bright Sky), sun and moon, and "on this day" (Wikipedia) for the masthead and almanac."""

import logging
from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from astral import LocationInfo, moon
from astral.sun import sun

from eilkurier.settings import Settings

log = logging.getLogger(__name__)

_ICONS = {
    "de": {
        "clear-day": "Sonnig",
        "clear-night": "Klar",
        "partly-cloudy-day": "Wechselnd bewölkt",
        "partly-cloudy-night": "Wechselnd bewölkt",
        "cloudy": "Bedeckt",
        "fog": "Nebelig",
        "wind": "Windig",
        "rain": "Regnerisch",
        "sleet": "Schneeregen",
        "snow": "Schnee",
        "hail": "Hagel",
        "thunderstorm": "Gewitter",
    },
    "en": {
        "clear-day": "Sunny",
        "clear-night": "Clear",
        "partly-cloudy-day": "Partly cloudy",
        "partly-cloudy-night": "Partly cloudy",
        "cloudy": "Overcast",
        "fog": "Foggy",
        "wind": "Windy",
        "rain": "Rainy",
        "sleet": "Sleet",
        "snow": "Snow",
        "hail": "Hail",
        "thunderstorm": "Thunderstorms",
    },
}
_LABELS = {
    "de": {
        "wind": "Wind",
        "from": "aus",
        "sun": "Sonne",
        "moon": "Mond",
        "clock": "Uhr",
        "years_ago": "Heute vor {n} Jahren",
        "rain_later": "später Regen",
        "phases": ["Neumond", "zunehmend", "Vollmond", "abnehmend"],
        "dirs": ["N", "NO", "O", "SO", "S", "SW", "W", "NW"],
    },
    "en": {
        "wind": "Wind",
        "from": "from",
        "sun": "Sun",
        "moon": "Moon",
        "clock": "",
        "years_ago": "{n} years ago today",
        "rain_later": "rain later",
        "phases": ["New moon", "waxing", "Full moon", "waning"],
        "dirs": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
    },
}


def _labels(lang: str) -> dict[str, Any]:
    return _LABELS.get(lang, _LABELS["de"])


def weather(http: httpx.Client, settings: Settings, day: date, lang: str) -> dict[str, Any] | None:
    try:
        response = http.get(
            "https://api.brightsky.dev/weather",
            params={
                "lat": settings.latitude,
                "lon": settings.longitude,
                "date": day.isoformat(),
                "tz": settings.timezone,
            },
        )
        response.raise_for_status()
        hours = response.json().get("weather", [])
    except (httpx.HTTPError, ValueError) as exc:
        log.info("weather unavailable: %s", exc)
        return None
    return summarize_weather(hours, settings.location_name, lang)


def summarize_weather(hours: list[dict[str, Any]], place: str, lang: str) -> dict[str, Any] | None:
    """Daytime (07–21 h) summary of hourly Bright Sky records."""
    daytime = [h for h in hours if 7 <= int(h["timestamp"][11:13]) <= 21 and h.get("temperature") is not None]
    if not daytime:
        return None
    labels = _labels(lang)
    icons = _ICONS.get(lang, _ICONS["de"])
    temps = [h["temperature"] for h in daytime]
    icon = Counter(h.get("icon") for h in daytime if h.get("icon")).most_common(1)
    summary = icons.get(icon[0][0], "–") if icon else "–"
    first_half = daytime[: len(daytime) // 2]
    if not any(h.get("condition") == "rain" for h in first_half) and any(
        h.get("condition") == "rain" for h in daytime[len(daytime) // 2 :]
    ):
        summary += ", " + labels["rain_later"]
    winds = [h["wind_speed"] for h in daytime if h.get("wind_speed") is not None]
    directions = [h["wind_direction"] for h in daytime if h.get("wind_direction") is not None]
    wind = f"{labels['wind']} {round(sum(winds) / len(winds))} km/h" if winds else ""
    if directions and wind:
        sector = round((sum(directions) / len(directions)) / 45) % 8
        wind += f" {labels['from']} {labels['dirs'][sector]}"
    return {
        "place": place,
        "summary": summary,
        "temp_min": round(min(temps)),
        "temp_max": round(max(temps)),
        "wind": wind,
    }


def moon_phase_name(day: date, lang: str) -> str:
    phase = moon.phase(day)  # 0 .. 27.99
    names = _labels(lang)["phases"]
    if phase < 1.5 or phase >= 26.5:
        return names[0]
    if 13 <= phase < 15.5:
        return names[2]
    return names[1] if phase < 13 else names[3]


def on_this_day(http: httpx.Client, day: date, lang: str) -> tuple[int, str] | None:
    """A 'selected' Wikipedia event for this date, preferring round anniversaries."""
    try:
        response = http.get(
            f"https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/selected/{day.month:02d}/{day.day:02d}"
        )
        response.raise_for_status()
        events = [e for e in response.json().get("selected", []) if e.get("year") and e.get("text")]
    except (httpx.HTTPError, ValueError) as exc:
        log.info("on-this-day unavailable: %s", exc)
        return None
    if not events:
        return None
    events.sort(key=lambda e: ((day.year - e["year"]) % 25 != 0, (day.year - e["year"]) % 10 != 0))
    return events[0]["year"], events[0]["text"]


def almanac(http: httpx.Client | None, settings: Settings, day: date, lang: str) -> dict[str, str]:
    labels = _labels(lang)
    tz = ZoneInfo(settings.timezone)
    location = LocationInfo(
        settings.location_name, "", settings.timezone, settings.latitude, settings.longitude
    )
    entries: dict[str, str] = {}
    try:
        s = sun(location.observer, date=day, tzinfo=tz)
        entries[labels["sun"]] = f"{s['sunrise']:%H:%M} – {s['sunset']:%H:%M} {labels['clock']}".strip()
    except ValueError:  # polar day/night
        pass
    entries[labels["moon"]] = moon_phase_name(day, lang)
    if http is not None and (event := on_this_day(http, day, lang)):
        year, text = event
        entries[labels["years_ago"].format(n=day.year - year)] = text
    return entries


def local_now(settings: Settings) -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))
