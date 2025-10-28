# alunos/routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from pymongo.errors import DuplicateKeyError
import re

from flask import current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os, time

from ..extensions import mongo
from ..utils import oid, now, scrub, hash_password

from urllib.parse import urljoin

bp = Blueprint("alunos", __name__)

ALUNO_FIELDS = {
    # existentes
    "nome", "telefone", "cpf", "email", "senha", "interesse", "bio",
    "data_nascimento", "endereco",  # {cep,cidade,estado,rua,complemento}

    # perfil público
    "slug", "headline", "avatar_url", "banner_url",
    "especializacoes", "quer_ensinar", "quer_aprender",
    "skills",                 # [{nome, endossos}]
    "modalidades",            # ["Online","Presencial"]
    "valor_hora",             # número (BRL)
    "disponibilidade",        # {timezone, dias[], horarios[]}
    "experiencias",           # [{empresa,cargo,inicio,fim,descricao,link}]
    "formacao",               # [{instituicao,curso,inicio,fim,descricao}]
    "certificacoes",          # [{titulo,org,ano,link}]
    "idiomas",                # [strings]
    "projetos",               # [{titulo,resumo,link}]
    "links",                  # {linkedin,github,site,...}
    "visibilidade"            # "publico" | "privado"
}


# ---------------------------
# Helpers
# ---------------------------
def slugify(nome: str) -> str:
    if not nome:
        return "perfil"
    s = nome.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "perfil"


def ensure_unique_slug(base: str) -> str:
    base = base or "perfil"
    slug = base
    i = 2
    while mongo.db.alunos.count_documents({"slug": slug}, limit=1):
        slug = f"{base}-{i}"
        i += 1
    return slug


def normalize_list_maybe(value):
    """
    Aceita string, lista de strings, None. Retorna lista (ou None).
    """
    if value is None:
        return None
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    s = str(value).strip()
    if not s:
        return []
    parts = [p.strip() for p in s.split(",")]
    return [p for p in parts if p]


# ---------------------------
# Endpoints "me" (autenticado, usa JWT)
# ---------------------------
@bp.get("/me")
@jwt_required()
def get_me():
    uid = get_jwt_identity()
    _id = oid(uid)
    if not _id:
        return jsonify({"error": "invalid_token"}), 401

    doc = mongo.db.alunos.find_one({"_id": _id}, {})
    if not doc:
        # Auto-cria perfil esqueleto a partir do token (se houver claims)
        claims = get_jwt() or {}
        nome = (claims.get("nome") or "Aluno").strip()
        email = (claims.get("email") or "").strip().lower()

        base = slugify(nome)
        slug = ensure_unique_slug(base)

        novo = {
            "_id": _id,
            "nome": nome,
            "email": email,
            "slug": slug,
            "visibilidade": "publico",
            "created_at": now(),
            "updated_at": now(),
        }
        mongo.db.alunos.insert_one(novo)
        doc = novo

    return jsonify(scrub(doc))


@bp.put("/me")
@jwt_required()
def update_me():
    uid = get_jwt_identity()
    _id = oid(uid)
    if not _id:
        return jsonify({"error": "invalid_token"}), 401

    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in ALUNO_FIELDS and k != "email"}

    # senha -> senha_hash (opcional)
    if "senha" in data:
        nova = (data.get("senha") or "").strip()
        if nova:
            body["senha_hash"] = hash_password(nova)
    body.pop("senha", None)

    # normalizações de listas
    for f in ("interesse", "especializacoes", "quer_ensinar", "quer_aprender", "idiomas", "modalidades"):
        if f in body:
            body[f] = normalize_list_maybe(body.get(f))

    # slug único se veio
    if "slug" in body and body["slug"]:
        new_base = slugify(body["slug"])
        new_slug = new_base
        exists = mongo.db.alunos.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(new_base)
        body["slug"] = new_slug

    if not body:
        return jsonify({"error": "no_fields_to_update"}), 400

    body["updated_at"] = now()
    mongo.db.alunos.update_one({"_id": _id}, {"$set": body}, upsert=True)
    doc = mongo.db.alunos.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))


# ---------------------------
# CRUD clássico (admin / util)
# ---------------------------
@bp.post("/")
def create():
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in ALUNO_FIELDS}

    if not body.get("nome") or not data.get("email"):
        return jsonify({"error": "missing_fields", "required": ["nome", "email"]}), 400

    body["email"] = str(data["email"]).strip().lower()

    senha = data.get("senha")
    if senha:
        body["senha_hash"] = hash_password(senha)
    body.pop("senha", None)

    for f in ("interesse", "especializacoes", "quer_ensinar", "quer_aprender", "idiomas", "modalidades"):
        if f in body:
            body[f] = normalize_list_maybe(body.get(f))

    if not body.get("slug"):
        base = slugify(body.get("nome"))
        body["slug"] = ensure_unique_slug(base)
    else:
        base = slugify(body["slug"])
        body["slug"] = ensure_unique_slug(base)

    body["created_at"] = body["updated_at"] = now()

    try:
        res = mongo.db.alunos.insert_one(body)
    except DuplicateKeyError:
        if mongo.db.alunos.count_documents({"email": body["email"]}, limit=1):
            return jsonify({"error": "email_already_exists"}), 409
        return jsonify({"error": "slug_already_exists"}), 409

    doc = mongo.db.alunos.find_one({"_id": res.inserted_id}, {})
    return jsonify(scrub(doc)), 201


@bp.get("/")
def list_():
    args = request.args
    q = args.get("q")
    cidade = args.get("cidade")
    estado = args.get("estado")
    ensina = args.get("ensina")
    aprende = args.get("aprende")
    especializacao = args.get("especializacao")
    modalidade = args.get("modalidade")
    precoMin = args.get("precoMin", type=float)
    precoMax = args.get("precoMax", type=float)
    minRating = args.get("minRating", type=float)
    vis = args.get("vis", "publico")

    page = int(args.get("page", 1))
    limit = int(args.get("limit", 10))
    order = int(args.get("order", -1))
    sort = args.get("sort", "created_at")

    filt = {}
    if vis == "publico":
        filt["visibilidade"] = {"$ne": "privado"}

    if q:
        regex = {"$regex": q, "$options": "i"}
        filt["$or"] = [
            {"nome": regex},
            {"email": regex},
            {"bio": regex},
            {"headline": regex},
            {"especializacoes": regex},
            {"quer_ensinar": regex},
            {"quer_aprender": regex},
            {"skills.nome": regex},
        ]

    if cidade:  filt["endereco.cidade"] = {"$regex": f"^{cidade}$", "$options": "i"}
    if estado:  filt["endereco.estado"] = {"$regex": f"^{estado}$", "$options": "i"}
    if ensina:  filt["quer_ensinar"] = {"$regex": ensina, "$options": "i"}
    if aprende: filt["quer_aprender"] = {"$regex": aprende, "$options": "i"}
    if especializacao: filt["especializacoes"] = {"$regex": especializacao, "$options": "i"}
    if modalidade: filt["modalidades"] = {"$regex": f"^{modalidade}$", "$options": "i"}
    if precoMin is not None or precoMax is not None:
        rng = {}
        if precoMin is not None: rng["$gte"] = precoMin
        if precoMax is not None: rng["$lte"] = precoMax
        filt["valor_hora"] = rng
    if minRating is not None:
        filt["media_avaliacoes"] = {"$gte": float(minRating)}

    cur = (
        mongo.db.alunos.find(filt, {})
        .sort(sort, order)
        .skip((page - 1) * limit)
        .limit(limit)
    )
    total = mongo.db.alunos.count_documents(filt)
    return jsonify({"data": [scrub(d) for d in cur], "total": total, "page": page, "limit": limit})


@bp.get("/<id>")
@jwt_required()
def get_(id):
    from flask_jwt_extended import get_jwt, get_jwt_identity
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400

    doc = mongo.db.alunos.find_one({"_id": _id}, {})
    if doc:
        return jsonify(scrub(doc))

    uid = oid(get_jwt_identity())
    if uid and uid == _id:
        claims = get_jwt() or {}
        nome = (claims.get("nome") or "Aluno").strip()
        email = (claims.get("email") or "").strip().lower()
        base = slugify(nome)
        slug = ensure_unique_slug(base)
        novo = {
            "_id": _id, "nome": nome, "email": email, "slug": slug,
            "visibilidade": "publico", "created_at": now(), "updated_at": now()
        }
        mongo.db.alunos.insert_one(novo)
        return jsonify(scrub(novo)), 201

    return jsonify({"error": "not_found"}), 404

# ----------- Perfil público por slug (sem JWT) -----------
@bp.route("/slug/<slug>", methods=["GET"])
@bp.route("/slug/<slug>/", methods=["GET"])   # aceita a barra final também
def get_public_by_slug(slug):
    doc = mongo.db.alunos.find_one({"slug": slug, "visibilidade": {"$ne": "privado"}}, {})
    if not doc: return jsonify({"error":"not_found"}), 404
    safe = scrub(doc)
    safe.pop("cpf", None); safe.pop("telefone", None); safe.pop("email", None)
    return jsonify(safe)


@bp.get("/me")
@jwt_required()
def me():
    """Retorna o aluno logado para checar slug/visibilidade."""
    _id = oid(get_jwt_identity())
    if not _id: return jsonify({"error":"invalid_identity"}), 400
    doc = mongo.db.alunos.find_one({"_id": _id}, {})
    if not doc: return jsonify({"error":"not_found"}), 404
    return jsonify(scrub(doc))


@bp.post("/me/publish")
@jwt_required()
def publish_me():
    """Gera/ajusta slug e marca visibilidade como 'publico'."""
    _id = oid(get_jwt_identity())
    if not _id: return jsonify({"error":"invalid_identity"}), 400
    d = mongo.db.alunos.find_one({"_id": _id}, {})
    if not d: return jsonify({"error":"not_found"}), 404

    # slug: se não tiver ou vier vazio, gera a partir do nome; se tiver, normaliza e garante unicidade
    base = slugify(d.get("slug") or d.get("nome") or "perfil")
    new_slug = ensure_unique_slug(base)

    mongo.db.alunos.update_one(
        {"_id": _id},
        {"$set": {
            "slug": new_slug,
            "visibilidade": "publico",
            "updated_at": now(),
        }}
    )
    doc = mongo.db.alunos.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))

@bp.put("/<id>")
@jwt_required()
def update(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400

    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in ALUNO_FIELDS and k != "email"}

    if "senha" in data:
        nova = (data.get("senha") or "").strip()
        if nova:
            body["senha_hash"] = hash_password(nova)
    body.pop("senha", None)

    for f in ("interesse", "especializacoes", "quer_ensinar", "quer_aprender", "idiomas", "modalidades"):
        if f in body:
            body[f] = normalize_list_maybe(body.get(f))

    if "slug" in body and body["slug"]:
        new_base = slugify(body["slug"])
        new_slug = new_base
        exists = mongo.db.alunos.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(new_base)
        body["slug"] = new_slug

    if not body:
        return jsonify({"error": "no_fields_to_update"}), 400

    body["updated_at"] = now()
    r = mongo.db.alunos.update_one({"_id": _id}, {"$set": body})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404

    doc = mongo.db.alunos.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))


@bp.delete("/<id>")
@jwt_required()
def delete(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    r = mongo.db.alunos.delete_one({"_id": _id})
    return ("", 204) if r.deleted_count else (jsonify({"error": "not_found"}), 404)


# ---------------------------
# Ações sociais (opcionais)
# ---------------------------
@bp.post("/<id>/endorse")
@jwt_required()
def endorse_skill(id):
    _id = oid(id)
    data = request.get_json(force=True) or {}
    skill = (data.get("skill") or "").strip()
    if not _id or not skill:
        return jsonify({"error": "invalid"}), 400

    r = mongo.db.alunos.update_one(
        {"_id": _id, "skills.nome": skill},
        {"$inc": {"skills.$.endossos": 1}}
    )
    if r.matched_count == 0:
        mongo.db.alunos.update_one(
            {"_id": _id},
            {"$push": {"skills": {"nome": skill, "endossos": 1}}}
        )
    return jsonify({"ok": True})


@bp.post("/<id>/review")
@jwt_required()
def add_review(id):
    _id = oid(id)
    d = request.get_json(force=True) or {}

    try:
        nota = int(d.get("nota", 0))
    except Exception:
        nota = 0
    if nota < 1 or nota > 5:
        return jsonify({"error": "invalid_rating"}), 400

    rev = {
        "autor_id": oid(d.get("autor_id")) or get_jwt_identity(),
        "nota": nota,
        "comentario": (d.get("comentario") or "").strip(),
        "data": now()
    }
    mongo.db.alunos.update_one({"_id": _id}, {"$push": {"avaliacoes": rev}})

    doc = mongo.db.alunos.find_one({"_id": _id}, {"avaliacoes": 1})
    notas = [int(r.get("nota", 0)) for r in (doc.get("avaliacoes") or []) if isinstance(r.get("nota", 0), (int, float))]
    media = round(sum(notas) / len(notas), 2) if notas else None
    mongo.db.alunos.update_one({"_id": _id}, {"$set": {"media_avaliacoes": media}})

    return jsonify({"ok": True, "media": media})

ALLOWED_IMG = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
MAX_BYTES = 2 * 1024 * 1024

def _allowed_img(mimetype: str) -> bool:
    return (mimetype or "").lower() in ALLOWED_IMG

def _save_avatar(file_storage, aluno_id: str) -> str:
    upload_root = current_app.config["UPLOAD_ROOT"]
    subdir = os.path.join("avatars", "alunos")
    dest_dir = os.path.join(upload_root, subdir)
    os.makedirs(dest_dir, exist_ok=True)

    fn = secure_filename(file_storage.filename or "avatar")
    _, ext = os.path.splitext(fn)
    ext = ext.lower() or ".jpg"
    ts = int(time.time())
    final_name = f"{aluno_id}_{ts}{ext}"
    abs_path = os.path.join(dest_dir, final_name)

    file_storage.save(abs_path)
    return f"{subdir}/{final_name}".replace("\\", "/")

def _avatar_url(rel_path: str) -> str:
    # devolve URL ABSOLUTA, ex.: http://localhost:5000/uploads/avatars/alunos/ID_123.jpg
    return urljoin(request.host_url, f"uploads/{rel_path}".replace("//", "/"))


def _ensure_self(id_str):
    _id = oid(id_str)
    if not _id:
        return None, (jsonify({"error": "invalid_id"}), 400)
    me = oid(get_jwt_identity())
    if not me or str(me) != str(_id):
        return None, (jsonify({"error": "forbidden"}), 403)
    return _id, None

@bp.route("/<id>/avatar", methods=["POST", "OPTIONS"])
@bp.route("/<id>/avatar/", methods=["POST", "OPTIONS"])
@jwt_required()
def upload_avatar_alunos_namespace(id):
    _id, err = _ensure_self(id)
    if err: return err

    f = request.files.get("file") or request.files.get("avatar")
    if not f:
        return jsonify({"error": "no_file"}), 400

    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > MAX_BYTES:
        return jsonify({"error": "file_too_large", "limit": MAX_BYTES}), 413

    if not _allowed_img(f.mimetype):
        return jsonify({"error": "unsupported_type", "mimetype": f.mimetype}), 415

    rel = _save_avatar(f, str(_id))
    url = _avatar_url(rel)

    mongo.db.alunos.update_one({"_id": _id}, {"$set": {"avatar_url": url, "updated_at": now()}}, upsert=True)
    doc = mongo.db.alunos.find_one({"_id": _id}, {})
    out = scrub(doc); out["avatarUrl"] = url
    return jsonify({"ok": True, "avatarUrl": url, "user": out}), 200