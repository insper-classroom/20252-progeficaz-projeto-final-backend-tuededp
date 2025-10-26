# api/chats.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId
from datetime import datetime
from ..extensions import mongo  # ajuste o import conforme seu projeto
from ..utils import scrub  # converte _id -> id, etc. (igual você usa em alunos)

bp = Blueprint("chats", __name__)

def oid(x):
  try:
    return ObjectId(x)
  except Exception:
    return None

def now():
  return datetime.utcnow()

def user_public(doc):
  # normalize do usuário para o front
  if not doc: return None
  return {
    "id": str(doc["_id"]),
    "nome": doc.get("nome"),
    "email": doc.get("email"),
    "bio": doc.get("bio"),
    "tipo": doc.get("tipo"),  # "prof" | "aluno"
  }

def conversation_payload(conv, me_id):
  # encontra o 'other' e monta resposta
  members = conv["members"]
  other_id = members[0] if members[1] == me_id else members[1]
  other_doc = mongo.db.usuarios.find_one({"_id": other_id}, {"nome":1,"email":1,"bio":1,"tipo":1})
  return {
    "id": str(conv["_id"]),
    "members": [str(m) for m in members],
    "other": user_public(other_doc),
    "last_message": conv.get("last_message"),
    "created_at": conv.get("created_at"),
    "updated_at": conv.get("updated_at"),
  }

@bp.get("/")
@jwt_required()
def list_conversations():
  me = get_jwt_identity()
  me_id = oid(me) if isinstance(me, str) else oid(me.get("id") or me.get("_id"))
  cur = (mongo.db.conversations
         .find({"members": me_id})
         .sort("updated_at", -1))
  out = [conversation_payload(c, me_id) for c in cur]
  return jsonify(out)

@bp.post("/")
@jwt_required()
def create_or_get():
  me = get_jwt_identity()
  me_id = oid(me) if isinstance(me, str) else oid(me.get("id") or me.get("_id"))
  user_id = oid((request.json or {}).get("user_id"))
  if not user_id: return jsonify({"msg":"user_id obrigatório"}), 400
  if user_id == me_id: return jsonify({"msg":"não pode conversar consigo mesmo"}), 400

  # já existe?
  existing = mongo.db.conversations.find_one({"members": {"$all": [me_id, user_id]}})
  if existing:
    return jsonify(conversation_payload(existing, me_id))

  conv = {
    "members": [me_id, user_id],
    "last_message": None,
    "created_at": now(),
    "updated_at": now(),
  }
  ins = mongo.db.conversations.insert_one(conv)
  conv["_id"] = ins.inserted_id
  return jsonify(conversation_payload(conv, me_id)), 201

@bp.get("/<conv_id>/messages")
@jwt_required()
def list_messages(conv_id):
  me = get_jwt_identity()
  me_id = oid(me) if isinstance(me, str) else oid(me.get("id") or me.get("_id"))
  cid = oid(conv_id)
  if not cid: return jsonify({"msg":"id inválido"}), 400

  conv = mongo.db.conversations.find_one({"_id": cid, "members": me_id})
  if not conv: return jsonify({"msg":"conversa não encontrada"}), 404

  cur = mongo.db.messages.find({"conversation_id": cid}).sort("created_at", 1)
  out = []
  for m in cur:
    out.append({
      "id": str(m["_id"]),
      "text": m["text"],
      "from": str(m["from"]),
      "fromMe": m["from"] == me_id,
      "created_at": m["created_at"].isoformat() + "Z",
    })
  return jsonify(out)

@bp.post("/<conv_id>/messages")
@jwt_required()
def send_message(conv_id):
  me = get_jwt_identity()
  me_id = oid(me) if isinstance(me, str) else oid(me.get("id") or me.get("_id"))
  cid = oid(conv_id)
  if not cid: return jsonify({"msg":"id inválido"}), 400
  body = request.get_json() or {}
  text = (body.get("text") or "").strip()
  if not text: return jsonify({"msg":"texto vazio"}), 400

  conv = mongo.db.conversations.find_one({"_id": cid, "members": me_id})
  if not conv: return jsonify({"msg":"conversa não encontrada"}), 404

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
