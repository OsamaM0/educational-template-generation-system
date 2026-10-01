"""ai.knowledge_productions — the new collection beside questions, worksheets,
summaries and mindmaps. One record per lesson, keyed like its siblings.

The MongoDB validator is DERIVED from schema/knowledge_production.schema.json
(to_mongo_schema), so the file the tests validate against and the rules the
database enforces cannot drift apart.
"""
import json, pathlib
from datetime import datetime, timezone

# Shipped inside the package so kp/ works wherever it is copied (e.g. into the generator repo).
SCHEMA_PATH = pathlib.Path(__file__).resolve().parent / "knowledge_production.schema.json"

_BSON = {"string": "string", "integer": ["int", "long"], "number": ["double", "int", "long", "decimal"],
         "boolean": "bool", "array": "array", "object": "object", "null": "null"}
_DROP = {"$schema", "$id", "$defs", "format", "x-bson", "title"}


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def to_mongo_schema(node, defs=None):
    """JSON Schema → MongoDB $jsonSchema: inline $ref, type → bsonType, dates as BSON date."""
    if defs is None:
        defs = node.get("$defs", {})
    if isinstance(node, list):
        return [to_mongo_schema(n, defs) for n in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        return to_mongo_schema(defs[node["$ref"].split("/")[-1]], defs)
    out = {}
    if node.get("x-bson") == "date":
        out["bsonType"] = "date"
    elif "type" in node:
        types = node["type"] if isinstance(node["type"], list) else [node["type"]]
        flat = []
        for t in types:
            m = _BSON[t]
            flat += m if isinstance(m, list) else [m]
        out["bsonType"] = flat[0] if len(flat) == 1 else list(dict.fromkeys(flat))
    for k, v in node.items():
        if k in _DROP or k == "type":
            continue
        if k == "properties":
            out[k] = {p: to_mongo_schema(s, defs) for p, s in v.items()}
        elif k in ("items", "oneOf", "anyOf", "allOf", "not"):
            out[k] = to_mongo_schema(v, defs)
        else:
            out[k] = v
    return out


def mongo_validator():
    s = to_mongo_schema(load_schema())
    s["properties"]["_id"] = {}          # MongoDB adds it; additionalProperties:false must allow it
    return {"$jsonSchema": s}


INDEXES = [
    ([("document_uuid", 1)], {"unique": True, "name": "uniq_document_uuid"}),
    ([("document_idx", 1)], {"name": "document_idx"}),
    ([("custom_id", 1)], {"name": "custom_id"}),
    ([("products.goal_id", 1)], {"name": "products_goal_id"}),
    ([("products.review.status", 1)], {"name": "review_status"}),
]


def ensure_collection(db, name, validation_action="error"):
    """Create (or update) the collection with its validator and indexes. Idempotent."""
    v = mongo_validator()
    opts = {"validator": v, "validationLevel": "moderate", "validationAction": validation_action}
    # Not every server accepts validators: FerretDB and some DocumentDB versions answer
    # NotImplemented, and a user without collMod rights answers Unauthorized. The record is
    # validated in Python before every write anyway (save_record), so the database-side
    # validator is a second line of defence, not the only one.
    unsupported = "server-side validator unsupported here; records are validated in Python before writing"
    if name in db.list_collection_names():
        try:
            db.command({"collMod": name, **opts})
            action = "validator updated"
        except Exception as e:
            action = f"exists; {unsupported} ({e.__class__.__name__})"
    else:
        try:
            db.create_collection(name, **opts)
            action = "created with $jsonSchema validator"
        except Exception as e:
            db.create_collection(name)
            action = f"created; {unsupported} ({getattr(e, 'codeName', e.__class__.__name__)})"
    skipped_indexes = []
    for keys, index_opts in INDEXES:
        try:
            db[name].create_index(keys, **index_opts)
        except Exception as e:
            # Generation only needs document read/write. Some production users
            # intentionally lack createIndex even though an administrator has
            # already provisioned the collection. Do not block lesson creation
            # on that optional maintenance permission.
            skipped_indexes.append(f"{index_opts['name']} ({getattr(e, 'codeName', e.__class__.__name__)})")
    if skipped_indexes:
        action += f"; indexes unchanged: {', '.join(skipped_indexes)}"
    return action


def find_questions_record(db, col, doc):
    """ai.questions for this lesson, using the strongest available identity."""
    rec = db[col].find_one({"document_uuid": doc.uuid}) if doc.uuid else None
    if not rec and doc.idx:
        values = [doc.idx] + ([int(doc.idx)] if doc.idx.isdigit() else [])
        rec = db[col].find_one({"document_idx": {"$in": values}})
    if not rec and doc.custom_id:
        rec = db[col].find_one({"custom_id": doc.custom_id})
    return rec


def get_record(db, col, uuid):
    return db[col].find_one({"document_uuid": uuid})


class RecordInvalid(ValueError):
    pass


def check_record(record):
    """The JSON Schema, applied in Python — independent of what the server enforces."""
    import jsonschema
    doc = dict(record)
    doc.pop("_id", None)
    if isinstance(doc.get("generated_at"), datetime):
        doc["generated_at"] = doc["generated_at"].isoformat()
    errors = sorted(jsonschema.Draft202012Validator(load_schema()).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        raise RecordInvalid("; ".join(f"{'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in errors[:5]))
    from .production_validate import check_project
    for product in doc.get('products', []):
        if 'sections' not in product:
            continue
        refs = [q['question_ref'] for q in product['questions']]
        semantic = check_project({'sections':product['sections']}, {'question_refs':refs}, doc['language'])
        if len(refs) != len(set(refs)):
            semantic.append('Question display references must be unique.')
        if semantic:
            raise RecordInvalid(f"{product['id']}: " + '; '.join(semantic))


def prepare_record(record):
    """Timestamp and validate a record without requiring database access."""
    record = dict(record)
    record["generated_at"] = datetime.now(timezone.utc)
    check_record(record)
    return record


def save_record(db, col, record):
    record = prepare_record(record)
    db[col].replace_one({"document_uuid": record["document_uuid"]}, record, upsert=True)
    return record


def candidates(db, summaries_col, limit=None):
    """Lessons with summary content. Sibling availability is checked per lesson."""
    cur = db[summaries_col].find({}, {"document_uuid": 1, "document_idx": 1, "custom_id": 1, "_id": 0})
    if limit:
        cur = cur.limit(limit)
    out = []
    for row in cur:
        if row.get("document_uuid"):
            out.append((str(row["document_uuid"]), "uuid"))
        elif row.get("document_idx") is not None:
            out.append((str(row["document_idx"]), "idx"))
        elif row.get("custom_id"):
            out.append((str(row["custom_id"]), "custom_id"))
    return out
