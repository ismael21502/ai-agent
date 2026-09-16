import requests
from langchain_core.tools import tool
from datetime import datetime, timedelta
#TODO: Añadir getHourlyWeather y getWeatherForecast

def getCoordinates(location: str) -> dict: 
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=10&language=es&format=json"
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        results = response.json()["results"]
        if not results:
            return None
        return {
            "latitude": results[0]["latitude"],
            "longitude": results[0]["longitude"],
            "region": results[0]["admin1"],
            "city": results[0]["admin2"]
        }
    except requests.RequestException:
        return None
    
def getWeather(location: str) -> dict:
    coordinates = getCoordinates(location)
    if coordinates is None:
        return {
            "success": False,
            "error": f"Could not find location: {location}"
        }
    "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&daily=precipitation_probability_max&hourly=temperature_2m,precipitation_probability,precipitation,cloud_cover_high,cloud_cover_mid,cloud_cover_low,cloud_cover,relative_humidity_2m&timezone=auto"
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={coordinates["latitude"]}"
        f"&longitude={coordinates["longitude"]}"
        "&current=temperature_2m,relative_humidity_2m,"
        "precipitation,precipitation_probability,cloud_cover,wind_speed_10m&timezone=auto"
    )
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        print(response.json())
        current = response.json()["current"]
        return {
            "success": True,
            "city": coordinates["city"],
            "region": coordinates["region"],
            "temperature": current["temperature_2m"],
            "humidity_percent": current["relative_humidity_2m"],
            "precipitation": current["precipitation"],
            "precipitation_probability_percent": current["precipitation_probability"],
            "cloud_cover_percent": current["cloud_cover"],
            "wind_speed": current["wind_speed_10m"]
        }
    except requests.RequestException as e:
        return {
            "success": False,
            "error": str(e)
        }

def getHourlyWeatherRange(location: str, startDatetime:str, endDatetime: str) -> dict:
    startDatetime = startDatetime[:13] + ":00"
    endDatetime = endDatetime[:13] + ":00"
    coordinates = getCoordinates(location)
    if coordinates is None:
        return {
            "success": False,
            "error": f"Could not find location: {location}"
        }
    url = ("https://api.open-meteo.com/v1/forecast"
            f"?latitude={coordinates["latitude"]}"
            f"&longitude={coordinates["longitude"]}"
            "&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability,precipitation,cloud_cover&timezone=auto"
            f"&start_hour={startDatetime}"
            f"&end_hour={endDatetime}")
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()["hourly"]
        return {
                "success": True,
                "city": coordinates["city"],
                "region": coordinates["region"],
                "datetime": data["time"],
                "temperature": data["temperature_2m"],
                "humidity_percent": data["relative_humidity_2m"],
                "precipitation": data["precipitation"],
                "precipitation_probability_percent": data["precipitation_probability"],
                "cloud_cover_percent": data["cloud_cover"],
                "wind_speed": data["wind_speed_10m"]
            }
    except requests.RequestException as e:
        return {
            "success": False,
            "error": str(e)
        }

@tool 
def getCurrentWeather(location: str) -> dict:
    """Get the current weather for a given location.
    Args:
        location (str): The location to get the weather for. (e.g., "Guadalajara, Jalisco")
    Returns:
        dict: A dictionary containing the weather information.
    """
    return getWeather(location)

@tool 
def getWeatherBetween(location: str, startDatetime: str, endDatetime: str) -> dict:
    """Get the hourly weather for a given location between two datetimes. 
        Use this when weather is needed for multiple hours within a period,
        such as "tomorrow morning", "tomorrow afternoon", or "from 2 PM to 6 PM".
        location (str): The location to get the weather for. (e.g., "Guadalajara, Jalisco")
        startDatetime (str): The start datetime in ISO 8601 format.
        endDatetime (str): The end datetime in ISO 8601 format.
    Returns:
        dict: A dictionary containing the weather information. 
    """
    start = datetime.fromisoformat(startDatetime)
    end = datetime.fromisoformat(endDatetime)
    if end < start:
        return {
            "success": False,
            "error": "End datetime must be after start datetime."
        }
    if(end - start > timedelta(hours=24)):
        return {
            "success": False,
            "error": "Time range must not exceed 24 hours."
        }
    
    data = getHourlyWeatherRange(location, startDatetime, endDatetime)
    if not data["success"]:
        return data
    formatedData = {}
    for i, time in enumerate(data["datetime"]):
        formatedData[time] = {
            "temperature": data["temperature"][i],
            "humidity_percent": data["humidity_percent"][i],
            "precipitation": data["precipitation"][i],
            "precipitation_probability_percent": data["precipitation_probability_percent"][i],
            "cloud_cover_percent": data["cloud_cover_percent"][i],
            "wind_speed": data["wind_speed"][i]
        }
    return {
        "success": True,
        "city": data["city"],
        "region": data["region"],
        "weather_data": formatedData
        }

@tool 
def getWeatherAt(location: str, targetDatetime: str) -> dict:
    """Get the weather for a given location at a specific datetime.
    Use this when weather is needed for a single specific moment.
    For multiple hours within a period, use getWeatherBetween.
    Args:
        location (str): The location to get the weather for. (e.g., "Guadalajara, Jalisco")
        targetDatetime (str): The datetime in ISO 8601 format.
    Returns:
        dict: A dictionary containing the weather information.
    """
    data = getHourlyWeatherRange(location, targetDatetime, targetDatetime)
    return {
                "success": True,
                "city": data["city"],
                "region": data["region"],
                "datetime": data["datetime"][0],
                "temperature": data["temperature"][0],
                "humidity_percent": data["humidity_percent"][0],
                "precipitation": data["precipitation"][0],
                "precipitation_probability_percent": data["precipitation_probability_percent"][0],
                "cloud_cover_percent": data["cloud_cover_percent"][0],
                "wind_speed": data["wind_speed"][0]
            }

# print(getWeatherBetween("Guadalajara, Jalisco", "2026-09-03T15:00", "2026-09-03T19:00"))
print(getWeather("Guadalajara, Jalisco"))
# print(getCoordinates("Guadalajara, Jalisco"))