# app/uploads/routes.py
import os, time
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from ..extensions import mongo
from ..utils import oid, now, scrub
from urllib.parse import urljoin

bp = Blueprint("uploads", __name__)

ALLOWED_IMG = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
MAX_BYTES = 2 * 1024 * 1024  # 2MB


def _allowed_img(mimetype: str) -> bool:
    return (mimetype or "").lower() in ALLOWED_IMG


# refatorado: salva em subpasta "alunos" ou "professores"
def _save_avatar(file_storage, usuario_id: str, subfolder: str) -> str:
    upload_root = current_app.config["UPLOAD_ROOT"]
    subdir = os.path.join("avatars", subfolder)  # ex.: avatars/alunos ou avatars/professores
    dest_dir = os.path.join(upload_root, subdir)
    os.makedirs(dest_dir, exist_ok=True)

    fn = secure_filename(file_storage.filename or "avatar")
    _, ext = os.path.splitext(fn)
    ext = ext.lower() or ".jpg"
    ts = int(time.time())
    final_name = f"{usuario_id}_{ts}{ext}"
    abs_path = os.path.join(dest_dir, final_name)

    file_storage.save(abs_path)
    return f"{subdir}/{final_name}".replace("\\", "/")


def _avatar_url(rel_path: str) -> str:
    # URL absoluta, ex.: http://localhost:5000/uploads/avatars/alunos/ID_123.jpg
    return urljoin(request.host_url, f"uploads/{rel_path}".replace("//", "/"))


def _ensure_self(id_str):
    _id = oid(id_str)
    if not _id:
        return None, (jsonify({"error": "invalid_id"}), 400)
    me = oid(get_jwt_identity())
    if not me or str(me) != str(_id):
        return None, (jsonify({"error": "forbidden"}), 403)
    return _id, None


def _validate_and_get_file():
    f = request.files.get("file") or request.files.get("avatar")
    if not f:
        return None, (jsonify({"error": "no_file"}), 400)

    # tamanho
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > MAX_BYTES:
        return None, (jsonify({"error": "file_too_large", "limit": MAX_BYTES}), 413)

    if not _allowed_img(f.mimetype):
        return None, (jsonify({"error": "unsupported_type", "mimetype": f.mimetype}), 415)

    return f, None


# ===================== ALUNOS =====================
@bp.route("/avatar/alunos/<id>", methods=["POST", "OPTIONS"])
@bp.route("/avatar/alunos/<id>/", methods=["POST", "OPTIONS"])
@jwt_required()
def upload_avatar_alunos(id):
    _id, err = _ensure_self(id)
    if err:
        return err

    f, ferr = _validate_and_get_file()
    if ferr:
        return ferr

    rel = _save_avatar(f, str(_id), "alunos")
    url = _avatar_url(rel)

    mongo.db.alunos.update_one({"_id": _id}, {"$set": {"avatar_url": url, "updated_at": now()}}, upsert=True)
    doc = mongo.db.alunos.find_one({"_id": _id}, {})
    out = scrub(doc)
    out["avatarUrl"] = url
    return jsonify({"ok": True, "avatarUrl": url, "user": out}), 200


# ===================== PROFESSORES =====================
@bp.route("/avatar/professores/<id>", methods=["POST", "OPTIONS"])
@bp.route("/avatar/professores/<id>/", methods=["POST", "OPTIONS"])
@jwt_required()
def upload_avatar_professores(id):
    _id, err = _ensure_self(id)
    if err:
        return err

    f, ferr = _validate_and_get_file()
    if ferr:
        return ferr

    rel = _save_avatar(f, str(_id), "professores")
    url = _avatar_url(rel)

    mongo.db.professores.update_one({"_id": _id}, {"$set": {"avatar_url": url, "updated_at": now()}}, upsert=True)
    doc = mongo.db.professores.find_one({"_id": _id}, {})
    out = scrub(doc)
    out["avatarUrl"] = url
    return jsonify({"ok": True, "avatarUrl": url, "user": out}), 200
