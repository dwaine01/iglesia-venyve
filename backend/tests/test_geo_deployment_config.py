"""Regresión: variables opcionales de Mapa 360 no pueden tumbar toda la API."""
import os
import subprocess


def test_server_imports_when_geo_environment_is_missing():
    environment = os.environ.copy()
    environment.update({
        "CENSUS_GEOCODER_URL": "", "CENSUS_GEOCODER_BENCHMARK": "",
        "GEO_CHURCH_ADDRESS": "", "GEO_CHURCH_LAT": "", "GEO_CHURCH_LNG": "",
    })
    result = subprocess.run(
        ["python", "-c", "import server; from geo_provider import geocoding_is_configured; assert not geocoding_is_configured()"],
        cwd="/app/backend", env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr