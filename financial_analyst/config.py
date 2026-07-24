from os import getenv

from dotenv import find_dotenv, load_dotenv


def load_env():
    _ = load_dotenv(find_dotenv())


def get_deepseek_api_key():
    load_env()
    deepseek_api_key = getenv("DEEPSEEK_API_KEY")
    return deepseek_api_key
