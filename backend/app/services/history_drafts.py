"""Durable audio queue and explicit save; no inferred facts enter assessment inputs."""
import asyncio
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
from uuid import UUID, uuid4
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.core.config import get_settings
from app.models.domain import User, Job, JobStatus
from app.models.history import HistoryDraft, HistoryClaim
from app.schemas.history import ClaimCreate, ClaimView, DraftApproval, DraftView, Language
from app.services import history, history_audio_store
from app.services.history_ai import HistoryModelGateway
from app.services.feature_common import FeatureError, aware, now, digest


def spool() -> Path:
    """Use an application-private runtime directory; never a public media location."""
    return Path(get_settings().history_audio_dir or f"{tempfile.gettempdir()}/trust-history-{os.getuid()}")


def _write_audio(data: bytes) -> Path:
    root = spool()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != os.getuid():
        raise FeatureError(503, "AUDIO_STORAGE_UNAVAILABLE", "Private audio storage is unavailable.")
    root.chmod(0o700)
    path = root / f"{uuid4()}.upload"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    return path


async def delete_audio(value: str | None) -> None:
    """Delete only files in this application's spool, avoiding arbitrary paths."""
    if value and value.startswith("s3://"):
        await history_audio_store.delete(value)
        return
    if value:
        path = Path(value)
        if path.parent.resolve() == spool().resolve():
            await asyncio.to_thread(path.unlink, missing_ok=True)


def view(row: HistoryDraft) -> DraftView:
    """Exclude temporary file paths and operation hashes from owner responses."""
    return DraftView(id=row.id, status=row.status, language=row.language, job_id=row.job_id, transcript=row.transcript, details=row.details, model_metadata=row.model_metadata, error_code=row.error_code, expires_at=row.expires_at, claim_id=row.claim_id)


async def owned_draft(session: AsyncSession, user: User, draft_id: UUID, *, lock: bool = False) -> HistoryDraft:
    """Check ownership and expire sensitive draft contents on read as well as sweep."""
    worker = await (history.lock_worker(session, user) if lock else history.own_worker(session, user))
    query = select(HistoryDraft).where(HistoryDraft.id == draft_id, HistoryDraft.worker_id == worker.id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise FeatureError(404, "DRAFT_NOT_FOUND", "Voice draft not found.")
    if aware(row.expires_at) <= now() and row.status != "saved":
        await delete_audio(row.audio_path)
        row.audio_path = None; row.transcript = None; row.details = None; row.status = "expired"
    return row


async def enqueue(session: AsyncSession, user: User, data: bytes, language: Language, job_id: UUID | None, operation: UUID) -> DraftView:
    """Bound uploads and persist an idempotent processing task before returning."""
    maximum = 3 if get_settings().deployment_mode == "serverless" else 5
    if not data or len(data) > maximum * 1024 * 1024:
        raise FeatureError(422, "AUDIO_SIZE_INVALID", f"Choose audio up to {maximum} MB.")
    worker = await history.lock_worker(session, user)
    fingerprint = hashlib.sha256(data + json.dumps({"language": language, "job_id": str(job_id)}, sort_keys=True).encode()).hexdigest()
    previous = await session.scalar(select(HistoryDraft).where(HistoryDraft.worker_id == worker.id, HistoryDraft.operation_id == operation))
    if previous:
        if previous.payload_hash != fingerprint:
            raise FeatureError(409, "IDEMPOTENCY_CONFLICT", "This operation was used for another recording.")
        return view(previous)
    if job_id:
        job = await session.get(Job, job_id)
        if job is None or job.worker_id != worker.id:
            raise FeatureError(404, "JOB_NOT_FOUND", "No owned job is available.")
        if job.status not in (JobStatus.COMPLETED, JobStatus.RELEASED):
            raise FeatureError(403, "JOB_INCOMPLETE", "Select a completed or released job.")
        if job.client_id is None:
            raise FeatureError(409, "CUSTOMER_UNATTRIBUTED", "The hiring customer has not been attributed.")
    pending = (await session.scalars(select(HistoryDraft.id).where(HistoryDraft.worker_id == worker.id, HistoryDraft.status.in_(["queued", "processing"])))).all()
    if len(pending) >= 2:
        raise FeatureError(429, "AUDIO_PENDING_LIMIT", "Wait for current recordings to finish.", 60)
    daily = (await session.scalars(select(HistoryDraft.id).where(HistoryDraft.worker_id == worker.id, HistoryDraft.created_at > now()-timedelta(days=1)))).all()
    if len(daily) >= 20:
        raise FeatureError(429, "AUDIO_DAILY_LIMIT", "Daily recording limit reached.", 3600)
    HistoryModelGateway()  # Never retain new audio without a processing provider.
    path = await history_audio_store.upload(data) if get_settings().history_audio_storage == "s3" else await asyncio.to_thread(_write_audio, data)
    row = HistoryDraft(worker_id=worker.id, job_id=job_id, operation_id=operation, payload_hash=fingerprint, language=language, audio_path=str(path), expires_at=now()+timedelta(hours=24))
    session.add(row)
    try:
        await session.flush()
    except Exception:
        await delete_audio(str(path))
        raise
    return view(row)


async def approve(session: AsyncSession, user: User, draft_id: UUID, payload: DraftApproval) -> ClaimView:
    """Atomic approval uses the draft's stable ID, so uncertain retries cannot duplicate work."""
    row = await owned_draft(session, user, draft_id, lock=True)
    if row.claim_id:
        saved = await session.get(HistoryClaim, row.claim_id)
        if saved.payload_hash != digest(ClaimCreate(details=payload.details, job_id=row.job_id).model_dump_json()):
            raise FeatureError(409, "IDEMPOTENCY_CONFLICT", "This draft was approved with different details.")
        return await history.claim_view(session, await history.owned_claim(session, user, row.claim_id))
    if row.status != "ready":
        raise FeatureError(409, "DRAFT_NOT_READY", "This recording is not ready for approval.")
    result = await history.create_claim(session, user, ClaimCreate(details=payload.details, job_id=row.job_id), row.id)
    row.claim_id = result.id; row.status = "saved"; row.details = None; row.transcript = None
    await delete_audio(row.audio_path); row.audio_path = None
    return result


async def normalize_audio(path: Path) -> Path:
    """Validate actual media and duration before bounded local-only ffmpeg decoding."""
    output = path.with_name(f"{path.stem}-{uuid4()}.wav")
    try:
        probe = await asyncio.create_subprocess_exec("ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", "matroska,webm,mov,mp4,m4a,3gp,3g2,mj2,mp3,wav,ogg,flac,aac", "-show_entries", "format=duration", "-of", "json", str(path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        stdout, _ = await asyncio.wait_for(probe.communicate(), 15)
        duration = float(json.loads(stdout)["format"]["duration"])
        if probe.returncode != 0 or not 0 < duration <= 60:
            raise ValueError("Invalid duration")
        process = await asyncio.create_subprocess_exec("ffmpeg", "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", "matroska,webm,mov,mp4,m4a,3gp,3g2,mj2,mp3,wav,ogg,flac,aac", "-i", str(path), "-t", "60", "-ac", "1", "-ar", "16000", "-f", "wav", "-y", str(output), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await asyncio.wait_for(process.wait(), 30)
        if process.returncode:
            raise ValueError("Invalid media")
        return output
    except FileNotFoundError as error:
        raise FeatureError(503, "MEDIA_PROCESSOR_UNAVAILABLE", "Audio processing requires ffmpeg and ffprobe.") from error
    except (ValueError, KeyError, asyncio.TimeoutError) as error:
        for child in (locals().get("probe"), locals().get("process")):
            if child and child.returncode is None:
                child.kill(); await child.wait()
        await delete_audio(str(output))
        raise FeatureError(422, "AUDIO_INVALID", "Use a valid recording up to 60 seconds.") from error


async def sweep(session: AsyncSession) -> None:
    """Remove expired transient content and crash-orphaned audio files."""
    rows = (await session.scalars(select(HistoryDraft).where(HistoryDraft.expires_at <= now(), HistoryDraft.status != "saved"))).all()
    for row in rows:
        await delete_audio(row.audio_path)
        row.audio_path = None; row.transcript = None; row.details = None; row.status = "expired"
    exhausted = (await session.scalars(select(HistoryDraft).where(HistoryDraft.status == "processing", HistoryDraft.lease_until < now(), HistoryDraft.attempts >= 3))).all()
    for row in exhausted:
        row.status = "failed"; row.error_code = "AUDIO_RETRY_EXHAUSTED"; row.lease_until = None
    root = spool()
    def cleanup() -> None:
        if root.exists():
            for path in root.iterdir():
                if path.suffix in {".upload", ".wav"} and path.stat().st_mtime < now().timestamp()-86400:
                    path.unlink(missing_ok=True)
    await asyncio.to_thread(cleanup)


async def process_one(factory: async_sessionmaker[AsyncSession]) -> bool:
    """Lease a durable task, run inference outside DB transactions, then save bounded output."""
    async with factory() as session:
        await sweep(session)
        row = await session.scalar(select(HistoryDraft).where(HistoryDraft.expires_at > now(), or_(HistoryDraft.status == "queued", and_(HistoryDraft.status == "processing", HistoryDraft.lease_until < now())), HistoryDraft.attempts < 3).order_by(HistoryDraft.created_at).with_for_update(skip_locked=True).limit(1))
        if row is None:
            await session.commit(); return False
        row.status = "processing"; row.lease_until = now()+timedelta(minutes=5); row.attempts += 1
        draft_id, language, original, attempt = row.id, row.language, row.audio_path, row.attempts
        await session.commit()
    normalized = None
    downloaded = None
    try:
        if not original:
            raise FeatureError(422, "AUDIO_MISSING", "The recording is unavailable.")
        downloaded = await history_audio_store.download(original, spool()) if original.startswith("s3://") else None
        normalized = await normalize_audio(downloaded or Path(original))
        gateway = HistoryModelGateway()
        transcript, metadata = await gateway.transcribe(normalized, language)
        details = await gateway.extract(transcript, language)
        accepted = False
        async with factory() as session:
            current = await session.get(HistoryDraft, draft_id, with_for_update=True)
            if current.status == "processing" and current.attempts == attempt and aware(current.expires_at) > now():
                accepted = True
                current.status = "ready"; current.transcript = transcript; current.details = details.model_dump(); current.model_metadata = {**metadata, "llm": "NCAIR1/N-ATLaS", "llm_revision": gateway.extraction_revision}; current.audio_path = None; current.lease_until = None
            await session.commit()
        if accepted:
            await delete_audio(original)
    except Exception as error:
        code = error.code if isinstance(error, FeatureError) else "AUDIO_PROCESSING_FAILED"
        async with factory() as session:
            current = await session.get(HistoryDraft, draft_id, with_for_update=True)
            if current.status == "processing" and current.attempts == attempt:
                current.status = "failed"; current.error_code = code; current.lease_until = None
            await session.commit()
    finally:
        if normalized:
            await delete_audio(str(normalized))
        if downloaded:
            await delete_audio(str(downloaded))
    return True
