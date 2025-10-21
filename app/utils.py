from bson.objectid import ObjectId
from flask import current_app
from datetime import datetime, timezone
import bcrypt

def oid(s):
    try: return ObjectId(s)
    except Exception: return None

def now():
    return datetime.now(timezone.utc)

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def scrub(doc):
    if not doc:
        return doc
    doc["_id"] = str(doc["_id"])
    doc.pop("senha", None)
    show_hash = current_app.config.get("SHOW_HASH", False)

    if show_hash:
        pass
    else:
        doc.pop("senha_hash", None)
    return doc
