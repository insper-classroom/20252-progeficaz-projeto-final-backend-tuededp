# app/chats/routes.py
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from datetime import datetime, timezone
from ..extensions import mongo
from ..utils import scrub, now  # usa seu now() tz-aware (UTC)

bp = Blueprint("chats", __name__)

# ----------------- helpers -----------------

def oid(x):
    # aceita string, ObjectId, ou dict {"$oid": "..."}
    if isinstance(x, ObjectId):
        return x
    if isinstance(x, dict) and "$oid" in x:
        x = x["$oid"]
    try:
        return ObjectId(str(x))
    except Exception:
        return None

def iso_z(dt):
    """
    Converte datetime (aware ou naive) para string ISO8601 com 'Z' no fim.
    - Se vier naive, assume UTC.
    """
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # .isoformat() -> 'YYYY-MM-DDTHH:MM:SS+00:00'; trocamos '+00:00' por 'Z'
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def _parse_since_iso(s: str):
    """
    Aceita '2025-10-27T20:38:46Z' ou com offset ('+00:00').
    Retorna datetime tz-aware em UTC.
    """
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def find_user_any(_id):
    if not _id:
        return None
    proj = {"nome": 1, "email": 1, "bio": 1, "tipo": 1}
    return (
        mongo.db.get_collection("usuarios").find_one({"_id": _id}, proj)
        or mongo.db.alunos.find_one({"_id": _id}, proj)
        or mongo.db.professores.find_one({"_id": _id}, proj)
    )

def user_public(doc):
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "nome": doc.get("nome"),
        "email": doc.get("email"),
        "bio": doc.get("bio"),
        "tipo": doc.get("tipo"),  # "prof" | "aluno"
    }

def conversation_payload(conv, me_id):
    members = conv["members"]
    # membros foram salvos como ObjectId ou string — toleramos ambos
    m0, m1 = members
    other_id = m0 if str(m1) == str(me_id) else m1
    other_oid = oid(other_id) or other_id
    other_doc = find_user_any(other_oid)

    # Completa/recupera last_message se estiver ausente
    lm = conv.get("last_message") or None
    if not lm or not lm.get("at"):
        last_msg = mongo.db.messages.find_one(
            {"conversation_id": conv["_id"]},
            sort=[("created_at", -1)],
        )
        if last_msg:
            lm = {
                "text": last_msg.get("text", ""),
                "at": iso_z(last_msg.get("created_at")),
                "from": str(last_msg.get("from")),
            }
        else:
            lm = None

    return {
        "id": str(conv["_id"]),
        "members": [str(m) for m in members],
        "other": user_public(other_doc),
        "last_message": lm,
        "created_at": iso_z(conv.get("created_at")),
        "updated_at": iso_z(conv.get("updated_at")),
    }

def get_me_oid():
    ident = get_jwt_identity()
    if isinstance(ident, str):
        return oid(ident)
    if isinstance(ident, dict):
        return oid(ident.get("id") or ident.get("_id"))
    return None

# ----------------- rotas -----------------

@bp.get("/health")
def health():
    return {"ok": True}, 200

# Lista conversas do usuário autenticado
@bp.route("/", methods=["GET"], strict_slashes=False)
@jwt_required()
def list_conversations():
    me_id = get_me_oid()
    cur = (
        mongo.db.conversations
        .find({"members": {"$in": [me_id, str(me_id)]}})
        .sort("updated_at", -1)
    )
    out = [conversation_payload(c, me_id) for c in cur]
    return jsonify(out)

# Preflight do POST /api/chats
@bp.route("/", methods=["OPTIONS"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def chats_preflight():
    return ("", 204)

# Cria/obtém conversa (não duplica)
@bp.route("/", methods=["POST"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
@jwt_required()
def create_or_get():
    me_id = get_me_oid()
    user_id_raw = (request.json or {}).get("user_id")
    user_id = oid(user_id_raw)
    if not user_id:
        return jsonify({"msg": "user_id obrigatório"}), 400
    if str(user_id) == str(me_id):
        return jsonify({"msg": "não pode conversar consigo mesmo"}), 400

    existing = mongo.db.conversations.find_one(
        {"members": {"$all": [me_id, user_id]}}
    ) or mongo.db.conversations.find_one(
        {"members": {"$all": [str(me_id), str(user_id)]}}
    )
    if existing:
        return jsonify(conversation_payload(existing, me_id)), 200

    now_ = now()  # tz-aware UTC
    conv = {
        "members": [me_id, user_id],
        "last_message": None,
        "created_at": now_,
        "updated_at": now_,
    }
    ins = mongo.db.conversations.insert_one(conv)
    conv["_id"] = ins.inserted_id
    return jsonify(conversation_payload(conv, me_id)), 201

# Mensagens: aceita /messages e /messages/ (GET e POST)
@bp.route("/<conv_id>/messages", methods=["GET", "OPTIONS"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def messages_preflight_or_get(conv_id):
    if request.method == "OPTIONS":
        return ("", 204)
    return _list_messages(conv_id)

@bp.route("/<conv_id>/messages/", methods=["GET", "OPTIONS"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def messages_trailing_preflight_or_get(conv_id):
    if request.method == "OPTIONS":
        return ("", 204)
    return _list_messages(conv_id)

@bp.route("/<conv_id>/messages", methods=["POST"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
@jwt_required()
def messages_post(conv_id):
    return _send_message(conv_id)

@bp.route("/<conv_id>/messages/", methods=["POST"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
@jwt_required()
def messages_post_trailing(conv_id):
    return _send_message(conv_id)

# ----------------- implementações internas -----------------

@jwt_required(optional=True)
def _list_messages(conv_id):
    me_id = get_me_oid()
    cid = oid(conv_id)
    if not cid:
        return jsonify({"msg": "id inválido"}), 400

    conv = mongo.db.conversations.find_one({
        "_id": cid,
        "members": {"$in": [me_id, str(me_id)]}
    })
    if not conv:
        return jsonify({"msg": "conversa não encontrada"}), 404

    filt = {"conversation_id": cid}

    # Incremental: since=ISO8601 ('...Z' ou com offset)
    since_raw = request.args.get("since")
    since_dt = _parse_since_iso(since_raw) if since_raw else None
    if since_dt:
        # Como salvamos created_at tz-aware UTC, a comparação é segura
        filt["created_at"] = {"$gt": since_dt}

    cur = mongo.db.messages.find(filt).sort("created_at", 1).limit(200)

    out = []
    for m in cur:
        out.append({
            "id": str(m["_id"]),
            "text": m["text"],
            "from": str(m["from"]),
            "fromMe": (me_id is not None) and (str(m["from"]) == str(me_id)),
            "created_at": iso_z(m.get("created_at")),
        })
    return jsonify(out)

def _send_message(conv_id):
    me_id = get_me_oid()
    cid = oid(conv_id)
    if not cid:
        return jsonify({"msg": "id inválido"}), 400

    body = request.get_json() or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"msg": "texto vazio"}), 400

    conv = mongo.db.conversations.find_one({
        "_id": cid,
        "members": {"$in": [me_id, str(me_id)]}
    })
    if not conv:
        return jsonify({"msg": "conversa não encontrada"}), 404

    created = now()  # tz-aware UTC
    msg = {
        "conversation_id": cid,
        "from": me_id,
        "text": text,
        "created_at": created,
        "read_by": [me_id],
    }
    ins = mongo.db.messages.insert_one(msg)

    mongo.db.conversations.update_one(
        {"_id": cid},
        {"$set": {
            "last_message": {
                "text": text,
                "at": iso_z(created),
                "from": str(me_id),
            },
            "updated_at": created,
        }}
    )

    return jsonify({
        "id": str(ins.inserted_id),
        "text": text,
        "from": str(me_id),
        "fromMe": True,
        "created_at": iso_z(created),
    }), 201
