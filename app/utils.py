from bson.objectid import ObjectId
from flask import current_app
from datetime import datetime, timezone
import bcrypt
import os

def oid(s):
    try: return ObjectId(s)
    except Exception: return None

def now():
    return datetime.now(timezone.utc)

def hash_password(plain: str) -> str:
    """Gera hash com bcrypt. Em testes, usa rounds menores para acelerar.

    Respeita variáveis de ambiente:
    - TEST_BCRYPT_ROUNDS (apenas em pytest) default=4
    - BCRYPT_ROUNDS (fora de pytest) default=12
    """
    rounds = 12
    if "PYTEST_CURRENT_TEST" in os.environ:
        rounds = int(os.getenv("TEST_BCRYPT_ROUNDS", "4"))
    else:
        rounds = int(os.getenv("BCRYPT_ROUNDS", "12"))
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds)).decode("utf-8")

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
