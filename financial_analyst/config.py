from os import getenv

from dotenv import find_dotenv, load_dotenv


def load_env():
    _ = load_dotenv(find_dotenv())


def get_deepseek_api_key():
    load_env()
    deepseek_api_key = getenv("DEEPSEEK_API_KEY")
    return deepseek_api_key


def get_cloudflare_credentials():
    """Return ``(account_id, api_token)`` for Cloudflare Workers AI.

    Both come from the environment (``CLOUDFLARE_ACCOUNT_ID`` and
    ``CLOUDFLARE_API_TOKEN`` in ``.env``). Either may be missing when the
    operator has not configured the embedding backend.
    """
    load_env()
    return getenv("CLOUDFLARE_ACCOUNT_ID"), getenv("CLOUDFLARE_API_TOKEN")
