"""Regression: the production quota-service builder must load .env before it
snapshots the quota limits.

Local dev runs uvicorn with QUOTA_* declared in the repo-root .env, but the
API process only loads that file through config.load_env() (which get_deepseek
/ get_cloudflare getters call lazily). If the quota service is built first it
reads empty os.environ and silently keeps the built-in defaults (verified
analyses = 3, not the .env value 50). get_quota_service now calls load_env()
before constructing QuotaService.
"""

import api.services as services
from financial_analyst.auth.quota import QuotaStore

QUOTA_ENV_VARS = (
    "QUOTA_ANALYSES_VERIFIED",
    "QUOTA_ANALYSES_UNVERIFIED",
    "QUOTA_CHAT_VERIFIED",
    "QUOTA_CHAT_UNVERIFIED",
)


def test_get_quota_service_loads_env_before_snapshotting_limits(tmp_path, monkeypatch):
    # Start from a scrubbed environment so the only way the snapshot sees
    # QUOTA_* = 50 is via get_quota_service() calling config.load_env().
    for name in QUOTA_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    def fake_load_env():
        monkeypatch.setenv("QUOTA_ANALYSES_VERIFIED", "50")
        monkeypatch.setenv("QUOTA_CHAT_VERIFIED", "50")

    monkeypatch.setattr(services.config, "load_env", fake_load_env)
    monkeypatch.setattr(
        services, "QuotaStore", lambda db: QuotaStore(str(tmp_path / "quota.db"))
    )
    monkeypatch.setattr(services, "_quota_service", None)

    service = services.get_quota_service()

    assert service.limit_for({"verified": True}, "analyses") == 50
    assert service.limit_for({"verified": True}, "chat") == 50

    monkeypatch.setattr(services, "_quota_service", None)
