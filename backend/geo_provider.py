"""Proveedor desacoplado de geocodificación; Census no requiere credenciales."""
import asyncio
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

import httpx


CENSUS_URL = os.environ.get("CENSUS_GEOCODER_URL")
CENSUS_BENCHMARK = os.environ.get("CENSUS_GEOCODER_BENCHMARK")
if not CENSUS_URL or not CENSUS_BENCHMARK:
    raise RuntimeError("CENSUS_GEOCODER_URL and CENSUS_GEOCODER_BENCHMARK are required")


@dataclass
class GeocodeResult:
    status: str
    latitude: float | None = None
    longitude: float | None = None
    confidence: str = "none"
    confidence_score: float = 0
    accuracy: str = "address_range_interpolated"
    matched_address: str | None = None
    provider_result_id: str | None = None
    provider_metadata: dict | None = None


class GeocodingProvider(Protocol):
    async def geocode(self, address: dict) -> GeocodeResult: ...


def _normalized(value: str | None) -> str:
    raw = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", " ", raw.upper()).strip()


def _street_parts(value: str) -> tuple[str | None, str]:
    match = re.match(r"^\s*(\d+[A-Z-]*)\s+(.+)$", value or "")
    return (match.group(1), match.group(2)) if match else (None, value or "")


def _confidence(address: dict, match: dict) -> tuple[float, str]:
    components = match.get("addressComponents") or {}
    number, street = _street_parts(address.get("street") or address.get("full_address") or "")
    returned_street = " ".join(filter(None, [
        components.get("preDirection"), components.get("streetName"),
        components.get("suffixType"), components.get("suffixDirection"),
    ]))
    expected_street = _normalized(street)
    actual_street = _normalized(returned_street)
    street_match = bool(expected_street and actual_street and (
        expected_street == actual_street or expected_street in actual_street or actual_street in expected_street
    ))
    state_match = _normalized(address.get("state")) == _normalized(components.get("state"))
    expected_zip = _normalized(address.get("zip"))
    zip_match = not expected_zip or expected_zip == _normalized(components.get("zip"))
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
        own_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=8)
        try:
            params = {"benchmark": CENSUS_BENCHMARK, "format": "json"}
            if address.get("street"):
                params.update({key: value for key, value in {
                    "street": address.get("street"), "city": address.get("city"),
                    "state": address.get("state"), "zip": address.get("zip"),
                }.items() if value})
                path = "/locations/address"
            else:
                params["address"] = address.get("full_address")
                path = "/locations/onelineaddress"
            last_error = None
            for attempt in range(3):
                try:
                    response = await client.get(f"{CENSUS_URL.rstrip('/')}{path}", params=params)
                    response.raise_for_status()
                    matches = response.json().get("result", {}).get("addressMatches", [])
                    if not matches:
                        return GeocodeResult(status="not_found")
                    if len(matches) > 1:
                        return GeocodeResult(status="ambiguous", provider_metadata={"match_count": len(matches)})
                    match = matches[0]
                    score, confidence = _confidence(address, match)
                    coordinates = match.get("coordinates") or {}
                    latitude = float(coordinates["y"]); longitude = float(coordinates["x"])
                    tiger = match.get("tigerLine") or {}
                    return GeocodeResult(
                        status="matched" if confidence == "high" else "needs_verification",
                        latitude=latitude, longitude=longitude, confidence=confidence,
                        confidence_score=round(score, 3), matched_address=match.get("matchedAddress"),
                        provider_result_id=str(tiger.get("tigerLineId") or "") or None,
                        provider_metadata={"benchmark": CENSUS_BENCHMARK, "side": tiger.get("side")},
                    )
                except (httpx.TimeoutException, httpx.HTTPStatusError, ValueError, KeyError) as error:
                    last_error = error
                    if attempt < 2:
                        await asyncio.sleep(0.35 * (2 ** attempt))
            return GeocodeResult(status="provider_error", provider_metadata={"error_type": type(last_error).__name__})
        finally:
            if own_client:
                await client.aclose()


_provider_override: GeocodingProvider | None = None


def get_geocoding_provider() -> GeocodingProvider:
    return _provider_override or CensusGeocodingProvider()


def set_geocoding_provider_for_tests(provider: GeocodingProvider | None) -> None:
    global _provider_override
    _provider_override = provider