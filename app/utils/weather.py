import httpx
import time
from datetime import datetime, timezone
from statistics import mean


WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
}


def _map_weather_code(code: int) -> str:
    return WEATHER_CODE_MAP.get(code, f"Code {code}")


def fetch_weather(lat: float, lon: float, date_str: str) -> dict | None:
    """
    Fetch historical weather for a given latitude, longitude and date (YYYY-MM-DD)
    using Open-Meteo (free, no API key).

    Returns a summary dict or None on failure.
    """
    try:
        # Choose archive endpoint for historical dates, forecast endpoint for today/future
        try:
            req_date = datetime.fromisoformat(date_str).date()
        except Exception:
            req_date = datetime.now(timezone.utc).date()

        today = datetime.now(timezone.utc).date()
        if req_date < today:
            url = "https://archive-api.open-meteo.com/v1/archive"
        else:
            url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": float(lat),
            "longitude": float(lon),
            "start_date": date_str,
            "end_date": date_str,
            "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
            "timezone": "UTC",
        }

        resp = httpx.get(url, params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()

        hourly = data.get("hourly", {})
        temps = hourly.get("temperature_2m", [])
        prec = hourly.get("precipitation", [])
        winds = hourly.get("windspeed_10m", [])
        codes = hourly.get("weathercode", [])

        if not temps:
            return None

        avg_temp = round(mean(temps), 1)
        max_temp = round(max(temps), 1)
        total_precip = round(sum(prec), 1) if prec else 0.0
        avg_wind = round(mean(winds), 1) if winds else None

        condition = None
        if codes:
            # pick the most frequent weather code
            try:
                from collections import Counter

                most_common = Counter(codes).most_common(1)[0][0]
                condition = _map_weather_code(most_common)
            except Exception:
                condition = _map_weather_code(codes[0]) if codes else None

        return {
            "date": date_str,
            "latitude": float(lat),
            "longitude": float(lon),
            "avg_temp_c": avg_temp,
            "max_temp_c": max_temp,
            "total_precip_mm": total_precip,
            "avg_wind_kmh": avg_wind,
            "condition": condition,
            "provider": "open-meteo",
            "raw": data,
        }

    except Exception as e:
        print(f"Weather fetch error: {e}")
        return None


# Simple in-memory cache: key -> (timestamp, data)
_CACHE: dict[str, tuple[float, dict]] = {}


def fetch_weather_cached(
        lat: float, lon: float, date_str: str, cache_key: str | None = None, ttl_hours: int = 24
) -> dict | None:
    """
    Fetch weather with a simple in-memory cache. Cache key defaults to "lat:lon:date" but can be provided
    (e.g., "hike_123"). TTL is in hours.
    """
    key = cache_key or f"{lat}:{lon}:{date_str}"
    now = time.time()

    entry = _CACHE.get(key)
    if entry:
        ts, data = entry
        if now - ts < ttl_hours * 3600:
            return data

    data = fetch_weather(lat, lon, date_str)
    if data:
        _CACHE[key] = (now, data)
    return data


def clear_weather_cache(cache_key: str | None = None) -> None:
    """Clear the cache for a specific key or all cache if key is None."""
    if cache_key:
        _CACHE.pop(cache_key, None)
    else:
        _CACHE.clear()
