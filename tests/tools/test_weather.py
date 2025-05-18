import aiohttp
import pytest

from msm_assistant.utils.helper.tools.weather import Weather


# --- Test name() ---
def test_name():
    assert Weather.name() == "get_weather"


# --- Test get_definition() ---
def test_get_definition():
    tool = Weather()
    definition = tool.get_definition()

    # Root
    assert definition["type"] == "function"
    fn = definition["function"]
    assert fn["name"] == "get_weather"
    assert fn["description"].startswith("Get the weather")
    assert fn["strict"] is True

    # Params
    params = fn["parameters"]
    assert params["type"] == "object"
    assert params["required"] == ["city", "country"]
    assert params["additionalProperties"] is False

    props = params["properties"]
    assert "city" in props and "country" in props
    assert props["city"]["type"] == "string"
    assert "city name" in props["city"]["description"].lower()
    assert props["country"]["type"] == "string"
    assert "country code" in props["country"]["description"].lower()


# --- Test init() no-op ---
@pytest.mark.asyncio
async def test_init_is_noop():
    tool = Weather()
    assert await tool.init() is None


# --- Test get_weather() success & missing data ---
class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummySession:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url):
        return DummyResponse(self._payload)


@pytest.mark.asyncio
async def test_get_weather_success(monkeypatch):
    payload = {"current": {"temperature_2m": 12.34}}
    # Stub aiohttp.ClientSession to our DummySession
    monkeypatch.setattr(aiohttp, "ClientSession", lambda: DummySession(payload))

    temp = await Weather.get_weather(1.23, 4.56)
    assert temp == 12.34


@pytest.mark.asyncio
async def test_get_weather_missing_current(monkeypatch):
    # payload missing 'current'
    payload = {}
    monkeypatch.setattr(aiohttp, "ClientSession", lambda: DummySession(payload))
    with pytest.raises(KeyError):
        await Weather.get_weather(0, 0)


# --- Test execute() paths ---
class DummyLocation:
    def __init__(self, lat, lon):
        self.latitude = lat
        self.longitude = lon


@pytest.mark.asyncio
async def test_execute_success(monkeypatch):
    tool = Weather()
    # Stub geocode to return a known lat/lon
    monkeypatch.setattr(
        tool._geolocator, "geocode", lambda query: DummyLocation(10.0, 20.0)
    )

    # Stub get_weather to return a temperature
    async def fake_get_weather(lat, lon):
        assert (lat, lon) == (10.0, 20.0)
        return 5.5

    monkeypatch.setattr(Weather, "get_weather", staticmethod(fake_get_weather))

    result = await tool.execute({"city": "X", "country": "Y"})
    assert result == {"temperature": 5.5}


@pytest.mark.asyncio
async def test_execute_city_not_found(monkeypatch):
    tool = Weather()
    monkeypatch.setattr(tool._geolocator, "geocode", lambda query: None)
    result = await tool.execute({"city": "NoCity", "country": "Nowhere"})
    assert result == {"error": "City not found"}


@pytest.mark.asyncio
async def test_execute_no_temperature(monkeypatch):
    tool = Weather()
    monkeypatch.setattr(
        tool._geolocator, "geocode", lambda query: DummyLocation(0.0, 0.0)
    )

    # get_weather returns None to simulate API failure
    async def fake_none(lat, lon):
        return None

    monkeypatch.setattr(Weather, "get_weather", staticmethod(fake_none))

    result = await tool.execute({"city": "X", "country": "Y"})
    assert result == {"error": "Could not retrieve weather data"}
