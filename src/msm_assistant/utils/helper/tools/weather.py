import aiohttp
from geopy.geocoders import Nominatim

from .base import Tool


class Weather(Tool):
    def __init__(self):  #! consider making the description a parameter
        self._geolocator = Nominatim(user_agent="weather_tool")

    @classmethod
    def name(self) -> str:
        return "get_weather"

    async def init(self) -> None:
        pass

    @staticmethod
    async def get_weather(latitude, longitude):
        url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return data["current"]["temperature_2m"]

    async def execute(self, arguments: dict) -> dict:
        """
        Execute the weather tool.
        """
        city = arguments["city"]
        country = arguments["country"]

        location = self._geolocator.geocode(f"{city}, {country}")
        if location is None:
            return {"error": "City not found"}

        latitude = location.latitude
        longitude = location.longitude
        temperature = await self.get_weather(latitude, longitude)
        if temperature is None:
            return {"error": "Could not retrieve weather data"}
        return {
            "temperature": temperature,
        }

    def get_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": "Get the weather of a city in degrees Celsius.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name to get the weather for.",
                        },
                        "country": {
                            "type": "string",
                            "description": "The country code of the city.",
                        },
                    },
                    "required": ["city", "country"],
                    "additionalProperties": False,
                },
            },
        }
