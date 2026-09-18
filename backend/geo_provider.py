"""Proveedores desacoplados: Census primero, Geocodio como respaldo permanente."""
import asyncio
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

import httpx


CENSUS_URL = os.environ.get("CENSUS_GEOCODER_URL")
CENSUS_BENCHMARK = os.environ.get("CENSUS_GEOCODER_BENCHMARK")
GEOCODIO_URL = os.environ.get("GEOCODIO_API_URL")
GEOCODIO_KEY = os.environ.get("GEOCODIO_API_KEY")
GEOCODIO_TIMEOUT = float(os.environ.get("GEOCODIO_TIMEOUT_SECONDS") or "6")


def geocoding_is_configured() -> bool:
    return bool((CENSUS_URL and CENSUS_BENCHMARK) or (GEOCODIO_URL and GEOCODIO_KEY))


def geocoding_providers_status() -> dict:
    return {
        "census": bool(CENSUS_URL and CENSUS_BENCHMARK),
        "geocodio": bool(GEOCODIO_URL and GEOCODIO_KEY),
    }


@dataclass
class GeocodeResult:
    status: str
    latitude: float | None = None
    longitude: float | None = None
    confidence: str = "none"
    confidence_score: float = 0
    accuracy: str = "unknown"
    matched_address: str | None = None
    provider_result_id: str | None = None
    provider_metadata: dict | None = None
    provider: str = "census"


class GeocodingProvider(Protocol):
    async def geocode(self, address: dict) -> GeocodeResult: ...


def _normalized(value: str | None) -> str:
    raw = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", " ", raw.upper()).strip()


def _street_parts(value: str) -> tuple[str | None, str]:
    match = re.match(r"^\s*(\d+[A-Z-]*)\s+(.+)$", value or "")
    return (match.group(1), match.group(2)) if match else (None, value or "")


def _address_text(address: dict) -> str:
    if address.get("full_address"):
        return str(address["full_address"])
    return ", ".join(str(value) for value in [
        address.get("street"), address.get("city"), address.get("state"), address.get("zip"), "USA",
    ] if value)


def _census_confidence(address: dict, match: dict) -> tuple[float, str]:
    components = match.get("addressComponents") or {}
    number, street = _street_parts(address.get("street") or address.get("full_address") or "")
    returned_street = " ".join(filter(None, [components.get("preDirection"), components.get("streetName"), components.get("suffixType"), components.get("suffixDirection")]))
    expected_street, actual_street = _normalized(street), _normalized(returned_street)
    street_match = bool(expected_street and actual_street and (expected_street == actual_street or expected_street in actual_street or actual_street in expected_street))
    state_match = _normalized(address.get("state")) == _normalized(components.get("state"))
    expected_zip = _normalized(address.get("zip")); zip_match = not expected_zip or expected_zip == _normalized(components.get("zip"))
    house_match = False
    if number and number.isdigit():
        lower = str(components.get("fromAddress") or "").replace("-", "")
        upper = str(components.get("toAddress") or "").replace("-", "")
        if lower.isdigit() and upper.isdigit():
            house_match = min(int(lower), int(upper)) <= int(number) <= max(int(lower), int(upper))
    score = (0.35 if street_match else 0) + (0.2 if state_match else 0) + (0.25 if zip_match else 0) + (0.2 if house_match else 0)
    return score, "high" if score >= 0.9 else "medium" if score >= 0.75 else "low"


class CensusGeocodingProvider:
    name = "census"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def geocode(self, address: dict) -> GeocodeResult:
        if not CENSUS_URL or not CENSUS_BENCHMARK:
            return GeocodeResult(status="provider_error", provider="census", provider_metadata={"error_type": "configuration_missing"})
        own_client = self.client is None; client = self.client or httpx.AsyncClient(timeout=8)
        try:
            params = {"benchmark": CENSUS_BENCHMARK, "format": "json"}
            if address.get("street"):
                params.update({key: value for key, value in {"street": address.get("street"), "city": address.get("city"), "state": address.get("state"), "zip": address.get("zip")}.items() if value})
                path = "/locations/address"
            else:
                params["address"] = address.get("full_address"); path = "/locations/onelineaddress"
            last_error = None
            for attempt in range(3):
                try:
                    response = await client.get(f"{CENSUS_URL.rstrip('/')}{path}", params=params)
                    response.raise_for_status(); matches = response.json().get("result", {}).get("addressMatches", [])
                    if not matches: return GeocodeResult(status="not_found", provider="census")
                    if len(matches) > 1: return GeocodeResult(status="ambiguous", provider="census", provider_metadata={"match_count": len(matches)})
                    match = matches[0]; score, confidence = _census_confidence(address, match)
                    coordinates = match.get("coordinates") or {}; tiger = match.get("tigerLine") or {}
                    return GeocodeResult(
                        status="matched" if confidence == "high" else "needs_verification",
                        latitude=float(coordinates["y"]), longitude=float(coordinates["x"]),
                        confidence=confidence, confidence_score=round(score, 3), accuracy="address_range_interpolated",
                        matched_address=match.get("matchedAddress"), provider_result_id=str(tiger.get("tigerLineId") or "") or None,
                        provider_metadata={"benchmark": CENSUS_BENCHMARK, "side": tiger.get("side")}, provider="census",
                    )
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, ValueError, KeyError) as error:
                    last_error = error
                    if attempt < 2: await asyncio.sleep(0.35 * (2 ** attempt))
            return GeocodeResult(status="provider_error", provider="census", provider_metadata={"error_type": type(last_error).__name__})
        finally:
            if own_client: await client.aclose()


class GeocodioGeocodingProvider:
    name = "geocodio"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def geocode(self, address: dict) -> GeocodeResult:
        if not GEOCODIO_URL or not GEOCODIO_KEY:
            return GeocodeResult(status="provider_error", provider="geocodio", provider_metadata={"error_type": "configuration_missing"})
        own_client = self.client is None; client = self.client or httpx.AsyncClient(timeout=GEOCODIO_TIMEOUT)
        try:
            last_error = None
            for attempt in range(3):
                try:
                    response = await client.get(
                        GEOCODIO_URL,
                        params={"q": _address_text(address), "country": "US", "limit": 1},
                        headers={"Authorization": f"Bearer {GEOCODIO_KEY}"},
                    )
                    if response.status_code in {400, 401, 403}:
                        return GeocodeResult(status="provider_error", provider="geocodio", provider_metadata={"error_type": f"http_{response.status_code}"})
                    response.raise_for_status(); results = response.json().get("results", [])
                    if not results: return GeocodeResult(status="not_found", provider="geocodio")
                    match = results[0]; location = match.get("location") or {}
                    accuracy_score = float(match.get("accuracy") or 0); accuracy_type = match.get("accuracy_type") or "unknown"
                    confidence = "high" if accuracy_score >= 0.8 else "medium" if accuracy_score >= 0.65 else "low"
                    return GeocodeResult(
                        status="matched" if confidence == "high" else "needs_verification",
                        latitude=float(location["lat"]), longitude=float(location["lng"]), confidence=confidence,
                        confidence_score=round(accuracy_score, 3), accuracy=accuracy_type,
                        matched_address=match.get("formatted_address"),
                        provider_result_id=str(match.get("id") or match.get("formatted_address") or "") or None,
                        provider_metadata={"accuracy_type": accuracy_type}, provider="geocodio",
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as error:
                    last_error = error
                except httpx.HTTPStatusError as error:
                    last_error = error
                    if error.response.status_code not in {429, 500, 502, 503, 504}:
                        break
                except (ValueError, KeyError) as error:
                    last_error = error; break
                if attempt < 2: await asyncio.sleep(0.4 * (2 ** attempt))
            return GeocodeResult(status="provider_error", provider="geocodio", provider_metadata={"error_type": type(last_error).__name__})
        finally:
            if own_client: await client.aclose()


class FallbackGeocodingProvider:
    def __init__(self, census: GeocodingProvider | None = None, geocodio: GeocodingProvider | None = None):
        self.census = census or CensusGeocodingProvider(); self.geocodio = geocodio or GeocodioGeocodingProvider()

    async def geocode(self, address: dict) -> GeocodeResult:
        census_result = await self.census.geocode(address)
        if census_result.status == "matched": return census_result
        geocodio_result = await self.geocodio.geocode(address)
        attempts = [census_result.provider, geocodio_result.provider]
        metadata = {**(geocodio_result.provider_metadata or {}), "attempted_providers": attempts, "census_status": census_result.status}
        geocodio_result.provider_metadata = metadata
        if geocodio_result.status in {"matched", "needs_verification"}: return geocodio_result
        if census_result.latitude is not None and census_result.longitude is not None:
            census_result.provider_metadata = {**(census_result.provider_metadata or {}), "attempted_providers": attempts, "geocodio_status": geocodio_result.status}
            return census_result
        return geocodio_result


_provider_override: GeocodingProvider | None = None


def get_geocoding_provider() -> GeocodingProvider:
    return _provider_override or FallbackGeocodingProvider()


def set_geocoding_provider_for_tests(provider: GeocodingProvider | None) -> None:
    global _provider_override
    _provider_override = provider