"""Keep validated model output when MongoDB becomes unavailable after generation."""
import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from . import PROMPT_VERSION
from .bank import build_bank
from .content import open_content
from .store import check_record, find_questions_record, get_record, prepare_record, save_record


def pending_dir():
    return Path(os.getenv('KP_PENDING_DIR') or
                Path(__file__).resolve().parent.parent / 'logs' / 'pending-knowledge-productions')


def write_pending(record):
    """Validate and atomically spool a record without writing to MongoDB."""
    record = prepare_record(record)
    directory = pending_dir()
    directory.mkdir(parents=True, exist_ok=True)
    lesson_hash = hashlib.sha256(record['document_uuid'].encode()).hexdigest()[:12]
    path = directory / f'lesson-{lesson_hash}-{uuid.uuid4().hex}.json'
    temp = path.with_suffix('.tmp')
    payload = json.dumps(record, ensure_ascii=False, indent=2,
                         default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value))
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def restore_pending(path, db, settings, dry_run=False):
    """Import a queued record only while its summary, goals and bank still match."""
    path = Path(path)
    record = json.loads(path.read_text(encoding='utf-8'))
    check_record(record)
    doc = open_content(settings, db).get(record['document_uuid'], 'uuid')
    bank = build_bank(find_questions_record(db, settings.col_questions, doc) or {}, doc.goals)
    if (record['content_fingerprint'] != doc.fingerprint or
            record['bank_fingerprint'] != bank.fingerprint or
            record['prompt_version'] != PROMPT_VERSION):
        raise ValueError('Pending record is stale; regenerate this lesson from current source records.')
    if get_record(db, settings.col_knowledge, doc.uuid):
        raise ValueError('A stored production already exists; inspect it before importing pending output.')
    if dry_run:
        return record
    record.pop('generated_at', None)
    saved = save_record(db, settings.col_knowledge, record)
    path.unlink()
    return saved
