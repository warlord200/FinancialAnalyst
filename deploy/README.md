# Deploying FinancialAnalyst (T14)

One always-on server: the API, the built React app, and the background
worker all run on the Azure for Students VM, with Caddy serving HTTPS.
SQLite and Chroma live on the VM's persistent disk under the app dir, so
they survive restarts and deploys.

## What runs where

| Process | Systemd unit | Command |
|---|---|---|
| API (FastAPI) | `financial-analyst-api.service` | `uvicorn api.main:app` on `127.0.0.1:8000` |
| Worker (ingest jobs) | `financial-analyst-worker.service` | `python -m api.worker` |
| Web server / HTTPS | Caddy | serves `web/dist`, proxies `/api/*` to the API |

The API enqueues ingest jobs and the worker runs them. Jobs live in a
shared SQLite table (`storage/jobs.db`); if the worker restarts mid-job,
it requeues the interrupted job on startup. Set `JOB_RUNNER=worker` in
`.env` on the server. For single-process local development leave
`JOB_RUNNER` unset (default `thread`).

## Files

- `setup.sh` — one-shot provisioning (packages, venv, build, units). Run
  as root on the VM with `DOMAIN=... ./deploy/setup.sh`.
- `Caddyfile` — web-server config (the `DOMAIN` and `{{APP_DIR}}`
  placeholders are replaced by `setup.sh`). HTTPS is automatic via
  Let's Encrypt.
- `systemd/*.service` — API and worker units (the `{{APP_DIR}}` placeholder
  is replaced by `setup.sh`).
- `requirements-server.txt` — runtime Python deps for the server. The
  local eval/reranker stack (torch, sentence-transformers) is deliberately
  **not** installed here: embeddings run on Cloudflare and the LLM on
  DeepSeek. If you enable `RERANKER_MODEL`, install
  `sentence-transformers` too.
- `.env.example` — secret keys the server needs.

## Live checklist

1. **Provision the VM** (Azure for Students): a `B2ats_v2` (2 vCPU / 4 GB,
   x86) running **Ubuntu 24.04 LTS**, with a persistent OS disk. Open
   inbound ports **22** (SSH), **80**, and **443** in the network security
   group. Note the public IP.
2. **Pick the hostname.** Either buy/register a domain (free option: the
   GitHub Student Pack) and point an `A` record at the VM's public IP, or
   reuse Azure's own `<vm-name>.<region>.cloudapp.azure.com` name — both
   work with Let's Encrypt.
3. **SSH in and clone the repo** to `/opt/financial-analyst`
   (`sudo mkdir -p /opt/financial-analyst`). Use a deploy key or PAT; do
   not leave a token in the URL.
4. **Create `.env`** at the repo root from `deploy/.env.example`, with
   `JOB_RUNNER=worker` and the real DeepSeek/Cloudflare keys.
5. **Run the installer**:
   `cd /opt/financial-analyst && sudo DOMAIN=<hostname> ./deploy/setup.sh`.
6. **Verify**:
   - `curl -fsS https://<hostname>/health` → `{"status":"ok"}`
   - `systemctl status financial-analyst-api financial-analyst-worker`
   - Open the site: sign up, analyze a ticker, walk the 6-step flow, and
     confirm the ingest job progresses while the worker logs show it
     running.
7. **Acceptance for the ticket**: app over HTTPS on a public domain;
   signup/login/analyze/6-step/thesis work; jobs run in the worker process
   and survive an API restart (`sudo systemctl restart financial-analyst-api`
   mid-ingest and watch the worker pick the job back up after a
   `financial-analyst-worker` restart).

## Redeploying (code updates)

```bash
cd /opt/financial-analyst
sudo -u financial-analyst git pull
sudo -u financial-analyst .venv/bin/python -m pip install -r deploy/requirements-server.txt
sudo -u financial-analyst npm --prefix web ci && sudo -u financial-analyst npm --prefix web run build
sudo systemctl restart financial-analyst-api financial-analyst-worker
```

`storage/`, `data/`, and `chroma_db/` are local to the VM (not in git), so
user data and corpora are never touched by a deploy.

## Local development

Unchanged: run `uvicorn api.main:app` on `:8000` and `npm run dev` on
`:5173`. The Vite dev server proxies `/api/*` to `:8000`, and the built
app talks to `/api` on its own origin, so no cross-origin setup or
`VITE_API_BASE` is needed. Set `VITE_API_BASE` only to point a build at a
backend on another origin.
