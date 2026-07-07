import os
from dotenv import load_dotenv

load_dotenv()

def get_intervals_icu_api_url() -> str:
    base_url = os.getenv("INTERVALS_ICU_BASE_URL")
    api_path = os.getenv("INTERVALS_ICU_API")

    if not base_url:
        raise RuntimeError("INTERVALS_ICU_BASE_URL fehlt in .env")

    if not api_path:
        raise RuntimeError("INTERVALS_ICU_API fehlt in .env")
    
    return f"{base_url}{api_path}"

def get_intervals_icu_username() -> str:
    return os.getenv("INTERVALS_ICU_USER_NAME")

def get_intervals_icu_api_key() -> str:
    return os.getenv("INTERVALS_ICU_API_KEY")

def get_intervals_icu_athlete_id() -> str:
    return os.getenv("INTERVALS_ICU_ATHLETE_ID")