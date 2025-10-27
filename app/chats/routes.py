# app/chats/routes.py
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from datetime import datetime
from ..extensions import mongo
from ..utils import scrub

bp = Blueprint("chats", __name__)

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

def now():
    return datetime.utcnow()

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
    # members pode ter ObjectId ou string; normaliza para comparar
    m0, m1 = members
    other_id = m0 if str(m1) == str(me_id) else m1
    # converte para ObjectId se vier string
    other_oid = oid(other_id) or other_id
    other_doc = find_user_any(other_oid)
    return {
        "id": str(conv["_id"]),
        "members": [str(m) for m in members],
        "other": user_public(other_doc),
        "last_message": conv.get("last_message"),
        "created_at": conv.get("created_at"),
        "updated_at": conv.get("updated_at"),
    }

def get_me_oid():
    ident = get_jwt_identity()
    # seu login grava identity=str(_id), então isso cobre
    if isinstance(ident, str):
        return oid(ident)
    if isinstance(ident, dict):
        return oid(ident.get("id") or ident.get("_id"))
    return None

# --- health (opcional p/ debug) ---
@bp.get("/health")
def health():
    return {"ok": True}, 200

# --- Lista conversas (GET /api/chats ou /api/chats/) ---
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

# --- Preflight do POST /api/chats ---
@bp.route("/", methods=["OPTIONS"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def chats_preflight():
    return ("", 204)

# --- Cria/obtém conversa (POST /api/chats ou /api/chats/) ---
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

    # já existe? (tolera ObjectId e string)
    existing = mongo.db.conversations.find_one(
        {"members": {"$all": [me_id, user_id]}}
    ) or mongo.db.conversations.find_one(
        {"members": {"$all": [str(me_id), str(user_id)]}}
    )
    if existing:
        return jsonify(conversation_payload(existing, me_id)), 200

    conv = {
        "members": [me_id, user_id],
        "last_message": None,
        "created_at": now(),
        "updated_at": now(),
    }
    ins = mongo.db.conversations.insert_one(conv)
    conv["_id"] = ins.inserted_id
    return jsonify(conversation_payload(conv, me_id)), 201

# --- Mensagens: aceita /messages e /messages/ (GET e POST) ---
@bp.route("/<conv_id>/messages", methods=["GET", "OPTIONS"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def messages_preflight_or_get(conv_id):
    if request.method == "OPTIONS":
        return ("", 204)

    # GET messages
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

# --- implementações internas (compartilhadas) ---

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

    cur = mongo.db.messages.find({"conversation_id": cid}).sort("created_at", 1)
    out = []
    for m in cur:
        out.append({
            "id": str(m["_id"]),
            "text": m["text"],
            "from": str(m["from"]),
            "fromMe": (me_id is not None) and (str(m["from"]) == str(me_id)),
            "created_at": m["created_at"].isoformat() + "Z",
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

    msg = {
        "conversation_id": cid,
        "from": me_id,
        "text": text,
        "created_at": now(),
        "read_by": [me_id],
    }
    ins = mongo.db.messages.insert_one(msg)

    mongo.db.conversations.update_one(
        {"_id": cid},
        {"$set": {
            "last_message": {
                "text": text,
                "at": msg["created_at"].isoformat() + "Z",
                "from": str(me_id)
            },
            "updated_at": now()
        }}
    )

    return jsonify({
        "id": str(ins.inserted_id),
        "text": text,
        "from": str(me_id),
        "fromMe": True,
        "created_at": msg["created_at"].isoformat() + "Z",
    }), 201
