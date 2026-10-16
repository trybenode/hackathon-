# Real N-ATLAS inference with Vercel, private storage and external jobs

## Architecture and current status

Keep Next.js and FastAPI on the existing Vercel services project. Add a private
S3 audio bucket, an external job worker, and a separately hosted NVIDIA GPU
inference service. PostgreSQL's existing HistoryDraft queue/leases are the durable
job system; no public worker endpoint, browser API key or new queue broker is needed.

```
Browser -> Next.js proxy -> Vercel FastAPI -> private S3 upload
                             | PostgreSQL queued draft
                             v
External worker -> S3 download -> ffmpeg -> GPU gateway /asr -> /extract
                             | PostgreSQL ready draft
                             v
Browser polls -> edits draft -> explicitly approves unscored history
```

Hugging Face access is approved according to the operator. There is no GPU host
provisioned yet. Code and mocked contract tests are not proof of live inference.
Do not enable production flags until the real recording smoke and browser flow pass.
Unrelated frontend merge conflicts/local changes remain outside this integration.

## 1. Provision dependencies deliberately

Choose a GPU host capable of holding NCAIR1/N-ATLaS plus an ASR model, inference
cache and runtime overhead. Measure memory/latency on that host before promising
capacity. FP16 8-billion-parameter weights alone occupy roughly 16 GB, before those
overheads. NVIDIA drivers and Container Toolkit must support the installed PyTorch
wheel/CUDA runtime. Docker image requirements use the existing Transformers 4.x
range; freeze a tested dependency/model revision set after actual GPU acceptance.
No provider is provisioned and no chargeable resources are started by this code.

Create a dedicated private S3 bucket, enable Block Public Access, encryption and a
lifecycle rule on `history-audio/` expiring objects after one day (also abort incomplete
multipart uploads). Lifecycle deletion is eventual, not exact to the hour. App reads
expire drafts at 24 hours; worker sweeps and successful processing delete objects.
Lifecycle handles objects orphaned by database commit failure or worker outage.
Do not put identity documents under this lifecycle prefix. Use TLS and least-privilege
PutObject/GetObject/DeleteObject on this bucket/prefix, without public ACLs.
Compatible storage must support the AES256 server-side encryption upload header;
otherwise implement and test an explicit provider adapter before using it.

## 2. GPU gateway

Copy deploy/natlas.gateway.env.example to `.env.natlas-gateway` privately.
HF_TOKEN is the approved read token. Generate HISTORY_GATEWAY_KEY with
`openssl rand -hex 32`; the API's HISTORY_AI_API_KEY must equal it.
Never share the HF token with the frontend or Vercel public variables.

The server image builds from repository root:

```sh
docker build -f backend/Dockerfile.natlas -t trust-natlas:local .
docker compose -f deploy/natlas.compose.yml up -d --build gateway
```

The compose profile requests all GPUs and binds port 8091 to host loopback only.
Set up a managed TLS reverse proxy on a chosen domain to 127.0.0.1:8091. Proxy
timeouts must permit operator warmup/cold loading; disable request-body and
Authorization logging. Do not expose an unauthenticated model service. Keep
one Uvicorn worker: multiple processes duplicate model weights and GPU memory.
The mounted model cache contains gated weights; restrict its access accordingly.

`GET /health/live` reports only process liveness. Authenticated
`POST /warmup {"language":"yo"}` loads the official text model and selected ASR.
Authenticated `GET /health/ready?language=yo` reports ready only when both are resident.
Only one ASR stays cached; selecting another language replaces it. Warmup/download
requires time and disk; model loading is never silently replaced by fake results.
Optional HISTORY_LLM_REVISION / HISTORY_ASR_REVISION_EN/YO/HA/IG pin accepted commits.

## 3. External worker and Vercel configuration

Copy the worker template to `.env.natlas-worker`; merge it with all existing backend
production settings, including the SAME database as Vercel, origins and secrets.
Do not change database schema or migrate production implicitly. Use the explicit
existing migration runner if pending revisions are required.

Start the durable job consumer:

```sh
docker compose -f deploy/natlas.compose.yml up -d --build worker
```

The worker needs ffmpeg/ffprobe (provided by backend/Dockerfile), a private local
spool, S3 credentials and HTTPS gateway access. Its PostgreSQL leases, operation
keys, three-attempt bound, expiry and user approval behavior remain in force.
Uncertain uploads reconcile through existing draft receipts; retry an existing
failed draft instead of creating another claim. Monitor worker logs/heartbeat,
job age, retry exhaustion, storage cleanup and GPU memory/latency.

After worker/storage/GPU acceptance, merge deploy/natlas.vercel.env.example into
Vercel settings and redeploy. RUN_HISTORY_WORKER stays false on Vercel; external
execution is explicit via HISTORY_EXTERNAL_WORKER=true and HISTORY_AUDIO_STORAGE=s3.
The serverless guard still rejects in-process workers and speech. Speech storage
has not been migrated to S3; leave HISTORY_SPEECH_ENABLED=false.

Audio uploads use a 3 MiB serverless cap to leave space for multipart overhead
below Vercel's request limit; containers retain 5 MiB. Capabilities expose
`audio_max_bytes`; the existing VoiceCapture now reads it for file selection.
Compressed 60-second recording is still the duration limit; the external worker
converts it to finite mono 16-kHz WAV. The gateway uses 30-second ASR chunks so
longer valid uploads are not treated as a single short Whisper window.

## 4. Run a real inference check

On a trusted machine with httpx installed, export process variables without
printing secrets. Use an authorized recording, normalized to WAV:

```sh
ffmpeg -i consented-recording.webm -t 60 -ac 1 -ar 16000 consented-recording.wav
# Export HISTORY_AI_BASE_URL and HISTORY_AI_API_KEY securely first.
cd backend
python -m scripts.check_natlas_live --audio /private/path/consented-recording.wav \
  --language yo --target en
```

This warms models, performs real ASR, extraction and translation and prints only
model/revision metadata, text lengths, elapsed time and a transcript hash. It
creates no job/claim, does not expose the text, and is not an accuracy benchmark.
A Hugging Face access grant alone is not a hosted endpoint. Document the actual
successful result before claiming N-ATLAS is running in the deployment.

## 5. Browser acceptance and release gates

Use a valid worker session, record/upload real consented speech, see queued then
ready status, edit the draft and explicitly save it. Check source/target messages
only in an authorized confirmation thread. Test rejected access, link revocation,
failed GPU/storage, interrupted submission, idempotent retries and object cleanup.
Confirm no NormalizedOutcome, rating, job completion or trust score is created by
inference. Originals and worker corrections remain authoritative.

Native speakers must review negation, amounts, dates, names and accents/noise.
Candidate static page translations are separate from model inference. A warm
translation request has a 45-second upstream timeout to fit the current web
request budget; failures preserve originals. Keep GPU capacity warm for interactive
translation; cold loading may exceed this and should be handled before enabling.
Public capability fields indicate configuration, not continuous GPU health.

Rollback: disable HISTORY_AI_ENABLED on Vercel, redeploy, stop accepting new audio,
allow already queued jobs to finish/expire, and retain cleanup/lifecycle processing.
Manual history and previously approved claims remain available. Do not disable
origin, auth or provenance checks to make a demo pass.

## Primary sources

- Official LLM and access/terms: https://huggingface.co/NCAIR1/N-ATLaS
- Official ASR usage/context: https://huggingface.co/NCAIR1/Yoruba-ASR
- Vercel function limits: https://vercel.com/docs/functions/limitations

Observe each model's attached terms, attribution and active-user/commercial-use
conditions. Do not claim application language accuracy from model-card benchmarks.
