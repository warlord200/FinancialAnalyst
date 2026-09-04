# Free / student-credit hosting for the financial-analyst web app (Aug 2026)

Researched 2026-08-29 against primary sources (official pricing/docs pages). App needs: FastAPI + static React frontend, ChromaDB (persistent on-disk vector store) + SQLite, sentence-transformers bge-m3 (~570M params) on CPU, always-on background worker (SEC filings → embeddings), outbound calls to SEC EDGAR / yfinance / DeepSeek. Realistic budget: 2–4 GB RAM, a few vCPUs, a few GB disk, ALWAYS-ON (no sleep-after-idle).

## Update (4 Sep 2026): embedding moved off-box to Cloudflare Workers AI

The embed model (now **Qwen/Qwen3-Embedding-0.6B**, see `docs/adr/0001-single-embed-model-qwen3.md`) no longer runs on the host. It is served by **Cloudflare Workers AI** (free tier, 10,000 neurons/day; the model costs 1075 neurons/M tokens). AAPL's 403-chunk corpus is ~190 neurons per re-ingest — roughly 50 full re-ingests/day fit in the free tier. Consequences for this research:

- **The ~1.2 GB Qwen3 model no longer needs RAM or disk on the box**, and CPU embedding time (~19–20 min per AAPL re-ingest locally) is gone; a re-ingest is one batched API call (~1 min).
- The always-on worker now does SEC download + parsing + Chroma writes only; its main outbound cost is SEC EDGAR requests.
- Memory pressure drops to ChromaDB + SQLite + (optionally, behind `RERANKER_MODEL`) a ~2.3 GB cross-encoder loaded only when enabled.
- The ARM/no-ARM and swap decisions in the sections below were driven largely by the local embed model; with embedding hosted, a smaller VM (e.g. the 1 GB B1s or a 1 GB micro) becomes viable for the core app. The free-tier options that previously failed on RAM (Render free's 512 MB, Railway Free, Heroku Eco) are no longer ruled out purely by embedding RAM, but keep the other disqualifiers (ephemeral disk, sleep-after-idle, whitelisted egress) from the analysis below.
- Network-only budget: embeddings are free at this volume; the remaining always-on cost is the VM/disk itself.

## Stack feasibility notes (verified against primary sources)

- **ARM/aarch64 wheels — LOW risk, verified.** `torch 2.13.0` ships `manylinux_2_28_aarch64` wheels for cp310–cp314 (pypi.org/project/torch/#files). `onnxruntime 1.29.0` ships `manylinux_2_28_aarch64` wheels for cp311–cp314, including cp313 (pypi.org/project/onnxruntime/#files). `sentence-transformers` is pure Python on top of torch/transformers (no native code). So Ampere A1 (ARM) is workable. Caveat: pin recent versions and check transitive native deps (duckdb, tokenizers) against your exact lock file before committing to ARM.
- **Python 3.13**: supported by torch (cp313 wheels) and onnxruntime (cp313 wheels) — verified.
- **bge-m3 memory**: ~2.3 GB in fp32 just for weights. On a 4 GB VM you'll want int8 quantization or swap; on 8–16 GB it's comfortable.

## Options compared

| Option | Cost | Compute / RAM | Persistent disk | Always-on? | Fits this stack? | Duration & caveats |
|---|---|---|---|---|---|---|
| **Azure for Students** (B2ats_v2) | $0 (no card needed) + $100 credit | 750 h/mo free of B1s (1 vCPU/1 GB), B2pts_v2 (ARM 2 vCPU/4 GB), B2ats_v2 (AMD/x86 2 vCPU/4 GB) — run one 24/7 each | Managed OS disk billed from credit (~$2–4/mo) | Yes (always-on VM) | **Yes** (x86, no ARM risk; 4 GB is top of range) | 12 months for the 750 h free VMs; $100 credit valid 12 months; **renewable yearly while a student**; burstable CPU (fine for bursty indexing); non-commercial use only |
| **Oracle Cloud Always Free** (Ampere A1) | $0 (always free) | 2 OCPU + 12 GB RAM total (1,500 OCPU-h + 9,000 GB-h/mo), 2× AMD micro (1/8 OCPU, 1 GB) | 200 GB block volume (incl. boot) | Yes | **Yes** (12 GB headroom; ARM verified low-risk) | No expiry; requires credit card (no prepaid/virtual/PIN cards; signup failures common); **idle-reclaim**: instance reclaimed if CPU & network <20% and (A1) memory <20% over 7 days; "out of host capacity" errors are common on A1 |
| GitHub Student Pack | free | n/a | n/a | n/a | Partially | Verified current offers: Azure $100 (18+), **Heroku $13/mo × 24 mo**, Namecheap .me domain 1 yr, .TECH 1 yr, Name.com domain, Copilot, Codespaces, Camber (40 CPU-h/mo — not always-on). **DigitalOcean is NO LONGER in the pack** (was $200/12 mo historically). No AWS/AWS Educate in pack. |
| Heroku | no free tier (removed ~2022) | Eco $5/mo 0.5 GB (sleeps 30 min); Basic $7/mo 0.5 GB always-on | **Ephemeral filesystem** — ChromaDB/SQLite wiped on dyno recycle | Basic only | **No** (0.5 GB too small for bge-m3; no persistent disk) | GitHub pack credit ($13/mo) covers Basic dyno, but RAM+disk rule it out |
| Google Cloud | $300 credit / 90 days (card required) | e2-micro always-free (0.25 vCPU/1 GB) too small; spend credit on e2-standard-2 (2 vCPU/8 GB ≈ $52/mo) | Boot disk (30 GB free tier; bigger from credit) | Yes while credit lasts | Partial (good headroom, dies after 90 days) | Free Trial auto-closes at 90 days or when credit spent; 30-day grace; resources deleted after. No student-specific GCP credit program exists. |
| AWS | $100 + up to $100 earned credits (card required) | Credits valid 12 mo; Free-plan account **expires 6 months** or when credits run out | EBS billed from credits | Yes while credit lasts | Partial (t3.small 2 GB ≈ $15/mo, t3.medium 4 GB ≈ $30/mo → months of coverage) | New 2025-26 model replaced the old t3.micro 12-mo tier; AWS Educate is now training-only (no hosting credits); free-plan limited to "always free" offers |
| Render | free tier = 512 MB/0.1 CPU | sleeps after **15 min idle**; ephemeral fs (SQLite/ChromaDB wiped on spin-down); free Postgres expires 30 d | Persistent disk only on paid ($0.25/GB/mo) | No (free) | **No** on free tier | To stay awake: Standard $25/mo (2 GB/1 CPU) or Pro $85/mo (4 GB/2 CPU) |
| Fly.io | no meaningful free tier (2 VM-h trial) | shared-cpu-2x 2 GB ≈ $11.83/mo; 4 GB ≈ $22.22/mo; volumes $0.15/GB/mo; egress $0.02/GB | Volumes (persistent) | Yes (paid) | Yes if paying | Card required; cheap paid option, not free |
| Railway | Free plan $0/mo, $1 usage credit | max 1 vCPU/0.5 GB on Free (too small); usage metered ~$20/vCPU/mo + $10/GB | Volumes 500 MB max (Free), 5 GB (Hobby) | Yes | **No** (too small / too pricey) | Hobby $5/mo but a 2 GB service ≈ $40/mo usage |
| PythonAnywhere | Beginner free | 1 web app; **whitelisted outbound internet only** (blocks EDGAR/yfinance/DeepSeek); no always-on tasks; 512 MB storage | Persistent home dir | No free always-on | **No** | Developer $10/mo has 1 always-on task + 5 GB disk but 5,000 CPU-sec/day budget → continuous embedding gets tarpitted |
| Hugging Face Spaces | **Docker/Gradio spaces now require a paid plan to create** (PRO/Team/Org) | CPU Basic free hardware is 2 vCPU/16 GB, but only on paid plans now | **Ephemeral 50 GB disk** (reset on restart); free hardware sleeps after inactivity | No | **No** | Free accounts only static + up to 2 Gradio on ZeroGPU (GPU, sleeps). Persistent ChromaDB not possible for free |

## DigitalOcean detail (item 8)

- Droplets (pricing.digitalocean.com/pricing/droplets, effective Jan 1 2026, per-second billing): Basic 2 GB/1 vCPU **$12/mo**, 2 GB/2 vCPU **$18/mo**, 4 GB/2 vCPU **$24/mo**, 8 GB/4 vCPU **$48/mo**.
- **$200 credit math (hypothetical)**: 2 GB droplet → ~16.7 months; 4 GB droplet → ~8.3 months.
- **Reality check**: the $200/12-month GitHub Pack credit is **gone** (verified against education.github.com/pack). DO's own new-signup promo credits are short-lived (their FAQ says "often provides promotional credits for new users", typically ~60 days validity) — not a long-term plan. Paying out of pocket: $12–24/mo for a 2–4 GB always-on droplet is the simplest reliable paid option.

## Recommendation

**#1 — Microsoft Azure for Students** (B2ats_v2, 2 vCPU / 4 GB, x86). No credit card, always-on VM, persistent managed disk, free 750 h/mo compute for 12 months (run one 24/7), $100 credit covers disk/egress extras, renewable yearly while a student. x86 removes the ARM question entirely. Main caveat: 4 GB is at the top of the app's own estimate — run bge-m3 int8 or add swap. Burstable CPU suits periodic SEC-indexing bursts.

**Runner-up — Oracle Cloud Always Free (Ampere A1, 2 OCPU / 12 GB / 200 GB disk / 10 TB egress, no expiry)** if you have a credit card and want real headroom. ARM is verified low-risk (torch + onnxruntime ship aarch64 wheels). Caveats: card-verification friction at signup, occasional "out of host capacity" on A1, and Oracle reclaims "idle" instances (CPU+network+memory all <20% over 7 days) — the background worker must keep the box measurably busy.

**Honest caveats**
- Every truly free always-on option with persistent disk is either Azure (12-month renewable student) or Oracle (forever, needs a card, ARM + idle-reclaim). Nothing is both no-card *and* indefinite.
- The GitHub pack no longer includes DigitalOcean or AWS credits; Heroku's $13/mo pack credit can't run this stack (0.5 GB, ephemeral disk).
- GCP/AWS credits are 90-day/6-month stopgaps, not hosting homes.
- Render/Spaces/PythonAnywhere free tiers sleep, wipe disk, or block outbound — all disqualifying for an always-on background worker with persistent ChromaDB.
- Oracle card gotcha: no prepaid / virtual / single-use cards; a temporary authorization hold appears (removed in 3–5 days).
- ARM risk is low but not zero — validate your exact dependency lock (esp. duckdb, tokenizers) on an ARM box before relying on Oracle.

## Sources checked (primary)
- Azure for Students — azure.microsoft.com/en-us/free/students/; Azure free services — azure.microsoft.com/en-us/pricing/free-services/; B-series sizes — learn.microsoft.com/en-us/azure/virtual-machines/sizes-b-series-burstable
- Heroku pricing — heroku.com/pricing
- GitHub Student Developer Pack — education.github.com/pack
- Oracle Cloud Free Tier — oracle.com/cloud/free/; Always Free resources — docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Google Cloud Free Program — cloud.google.com/free; free-cloud-features — cloud.google.com/free/docs/free-cloud-features
- AWS Free Tier — aws.amazon.com/free/; Free Tier terms — aws.amazon.com/free/terms/; free-tier doc — docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html; AWS Educate — aws.amazon.com/education/awseducate/
- DigitalOcean Droplet pricing — digitalocean.com/pricing/droplets
- Render pricing — render.com/pricing; free tier — render.com/docs/free
- Fly.io pricing — fly.io/docs/about/pricing/; free trial — fly.io/docs/about/free-trial/
- Railway pricing — railway.com/pricing
- PythonAnywhere — pythonanywhere.com/pricing/
- Hugging Face Spaces — huggingface.co/docs/hub/spaces-overview
- PyPI: torch & onnxruntime wheel listings (aarch64 / Python 3.13)
