"""Shared HTTP helpers for external data sources."""

import time

import requests

DEFAULT_USER_AGENT = "FinancialAnalyst research@example.com"


class ExternalSourceError(Exception):
    pass


def get_with_retry(
    url: str,
    *,
    params: dict | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
    max_retries: int = 3,
    timeout: int = 30,
) -> requests.Response:
    headers = {"User-Agent": user_agent}
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = ExternalSourceError(
                    f"HTTP {resp.status_code} for {url}"
                )
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(2**attempt)
    raise ExternalSourceError(
        f"Failed to fetch {url} after {max_retries} attempts: {last_exc}"
    )
