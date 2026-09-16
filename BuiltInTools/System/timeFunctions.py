from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from langchain_core.tools import tool
import re
from tzlocal import get_localzone_name

# get_current_time()
# get_current_date()
# get_current_weekday()
# add_time()
# subtract_time()
# time_difference()

def parseDuration(duration: str) -> timedelta:
    pattern = r"(?:(\d+)d)?\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?"
    match = re.fullmatch(pattern, duration.strip())
    if not match:
        raise ValueError(
            "Invalid duration. Use formats such as '2h', '30m', "
            "'2h 30m', or '1d 4h 20m'."
        )
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    return timedelta(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )

def getCurrentTimezone():
    return get_localzone_name()

def getCurrentTime(localTimeZone: str = "America/Mexico_City") -> dict:
    #TODO: Añadir try/except
    weekDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    timeZone = ZoneInfo(localTimeZone)
    
    currentDateTime = datetime.now(timeZone)
    return {
        "datetime": currentDateTime.isoformat(),
        "date": currentDateTime.strftime("%Y-%m-%d"),
        "time": currentDateTime.strftime("%H:%M:%S"),
        "weekday": weekDays[currentDateTime.weekday()],
        "timezone": localTimeZone
    }
@tool 
def getCurrentTimeTool(localTimeZone: str = "America/Mexico_City") -> dict:
    """Get the current date and time in the configured local timezone.
        Args: 
            localTimeZone (str): IANA timezone of the location for which the
            current date and time should be returned.
        Return: 
            A dictionary containing the current datetime in ISO format, date,
            time, weekday, and timezone."""
    return getCurrentTime(localTimeZone)
#AddTime debería de recibir days, months, years, etc. en lugar de duration?
@tool
def addTime(time: str, duration: str) -> str:
    """Add a duration to a given datetime.
    Args:
        time: Time in datetime in ISO 8601 format.
        duration: Duration to add, using days, hours, minutes, and seconds.
            Examples: "2h", "30m", "2h 30m", "1d 4h".
    Returns:
        The resulting datetime.
    """
    delta = parseDuration(duration)
    try:
        current = datetime.fromisoformat(time)
        result = current + delta
        return result.isoformat()
    except ValueError:
        print("Invalid datetime format")

@tool
def substractTime(time: str, duration: str) -> str:
    """Substract a duration to a given datetime.
    Args:
        time: Time in datetime in ISO 8601 format.
        duration: Duration to add, using days, hours, minutes, and seconds.
            Examples: "2h", "30m", "2h 30m", "1d 4h".
    Returns:
        The resulting datetime.
    """
    delta = parseDuration(duration)
    try:
        current = datetime.fromisoformat(time)
        result = current - delta
        return result.isoformat()

    except ValueError:
        print("Invalid datetime format")

@tool
def timeDiff(time1: str, time2: str) -> str:
    """Get time difference between 2 datetimes in ISO 8601 format
    Args: 
        time1: First datetime
        time2: Second datetime
    Returns: 
        timedelta between the two datetimes."""
    return abs(datetime.fromisoformat(time2) - datetime.fromisoformat(time1))
# import requests

# response = requests.get(
#     "https://ipwho.is/",
#     timeout=3
# )

# print(response.status_code)
# print(response.json())


# print(getCurrentTime())
# print(addTime(getCurrentTime()["datetime"], "30m"))