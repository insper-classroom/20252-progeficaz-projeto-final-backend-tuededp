# professores/routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from pymongo.errors import DuplicateKeyError
import re

from ..extensions import mongo
from ..utils import oid, now, scrub, hash_password

bp = Blueprint("professores", __name__)

# Campos permitidos para professores (inclui os campos migrados)
PROF_FIELDS = {
    # básicos / pessoais
    "nome", "telefone", "cpf", "email", "senha", "saldo",
    "bio", "historico_academico_profissional",
    "data_nascimento", "endereco",

    # perfil público / metadata
    "slug", "visibilidade", "area", "headline", "avatar_url", "banner_url",

    # campos específicos de professor (migrados)
    "quer_ensinar",
    "especializacoes",
    "idiomas",
    "skills",                # [{nome, endossos}]
    "modalidades",
    "valor_hora",            # valor cobrado pelo professor (número)
    "disponibilidade",       # {timezone, dias[], horarios[]}
    "experiencias",          # [{empresa,cargo,inicio,fim,descricao,link}]
    "formacao",              # [{instituicao,curso,inicio,fim,descricao}]
    "certificacoes",         # [{titulo,org,ano,link}]
    "projetos",              # [{titulo,resumo,link}]
    "links"                  # {linkedin,github,site,...}
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
    while mongo.db.professores.count_documents({"slug": slug}, limit=1):
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


def maybe_number(v):
    """Converte string/num para float se possível, senão None."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


# ---------------------------
# CRUD / Endpoints
# ---------------------------

@bp.post("/")
def create():
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in PROF_FIELDS}

    if not body.get("nome") or not data.get("email"):
        return jsonify({"error": "missing_fields", "required": ["nome", "email"]}), 400

    body["email"] = str(data["email"]).strip().lower()
    body.setdefault("saldo", 0.0)
    body.setdefault("visibilidade", "publico")

    # normaliza listas (inclui idiomas)
    for f in ("especializacoes", "quer_ensinar", "skills", "modalidades", "idiomas"):
        if f in body:
            body[f] = normalize_list_maybe(body.get(f))

    # valor_hora -> número (se fornecido)
    if "valor_hora" in body:
        vh = maybe_number(body.get("valor_hora"))
        if vh is not None:
            body["valor_hora"] = vh
        else:
            body.pop("valor_hora", None)

    # slug
    if not body.get("slug"):
        base = slugify(body.get("nome"))
        body["slug"] = ensure_unique_slug(base)
    else:
        base = slugify(body["slug"])
        body["slug"] = ensure_unique_slug(base)

    senha = body.pop("senha", None)
    if senha:
        body["senha_hash"] = hash_password(senha)

    body["created_at"] = body["updated_at"] = now()

    try:
        res = mongo.db.professores.insert_one(body)
    except DuplicateKeyError:
        # tenta proteger email duplicado
        if mongo.db.professores.count_documents({"email": body["email"]}, limit=1):
            return jsonify({"error": "email_already_exists"}), 409
        return jsonify({"error": "duplicate_key"}), 409

    doc = mongo.db.professores.find_one({"_id": res.inserted_id}, {})
    return jsonify(scrub(doc)), 201


@bp.get("/")
def list_():
    q = request.args.get("q")
    cidade = request.args.get("cidade")
    estado = request.args.get("estado")
    area = request.args.get("area")
    ensina = request.args.get("ensina")   # mapear para quer_ensinar
    page = int(request.args.get("page", 1)); limit = int(request.args.get("limit", 10))
    order = int(request.args.get("order", -1)); sort = request.args.get("sort", "created_at")

    filt = {}
    if q:
        regex = {"$regex": q, "$options": "i"}
        filt["$or"] = [
            {"nome": regex},
            {"email": regex},
            {"bio": regex},
            {"historico_academico_profissional": regex},
            {"especializacoes": regex},
            {"quer_ensinar": regex},
            {"skills.nome": regex},
        ]
    if cidade: filt["endereco.cidade"] = {"$regex": f"^{cidade}$", "$options": "i"}
    if estado: filt["endereco.estado"] = {"$regex": f"^{estado}$", "$options": "i"}
    if area:
        filt["area"] = {"$regex": f"^{area}$", "$options": "i"}
    if ensina:
        filt["quer_ensinar"] = {"$regex": ensina, "$options": "i"}

    cur = (mongo.db.professores.find(filt, {})
           .sort(sort, order)
           .skip((page-1)*limit)
           .limit(limit))
    total = mongo.db.professores.count_documents(filt)
    return jsonify({"data": [scrub(d) for d in cur], "total": total, "page": page, "limit": limit})


@bp.get("/<id>")
def get_(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    doc = mongo.db.professores.find_one({"_id": _id}, {})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    return jsonify(scrub(doc))


@bp.get("/me")
@jwt_required()
def get_me():
    """Retorna o professor logado."""
    uid = get_jwt_identity()
    if not uid:
        return jsonify({"error": "invalid_token", "msg": "Token não contém identidade"}), 401

    _id = oid(uid)
    if not _id:
        # Tenta buscar pelo email do token
        claims = get_jwt() or {}
        email = claims.get("email")
        if email:
            prof = mongo.db.professores.find_one({"email": email})
            if prof:
                _id = prof["_id"]
            else:
                return jsonify({"error": "invalid_token", "msg": "Não foi possível identificar o professor"}), 401
        else:
            return jsonify({"error": "invalid_token", "msg": "Token inválido"}), 401

    # Verifica se o usuário é do tipo professor (aceita "professor" ou "prof")
    claims = get_jwt() or {}
    user_tipo = claims.get("tipo", "").lower()
    if user_tipo not in ["professor", "prof"]:
        return jsonify({"error": "forbidden", "msg": "Acesso permitido apenas para professores"}), 403

    doc = mongo.db.professores.find_one({"_id": _id}, {})
    if not doc:
        return jsonify({"error": "not_found"}), 404

    return jsonify(scrub(doc))


@bp.put("/me")
@jwt_required()
def update_me():
    """Atualiza o professor logado."""
    uid = get_jwt_identity()
    if not uid:
        return jsonify({"error": "invalid_token", "msg": "Token não contém identidade"}), 401

    _id = oid(uid)
    if not _id:
        # Tenta buscar o professor pelo email ou outro campo do token
        claims = get_jwt() or {}
        email = claims.get("email") or uid
        prof = mongo.db.professores.find_one({"email": email})
        if not prof:
            return jsonify({"error": "invalid_token", "msg": "Não foi possível identificar o professor"}), 401
        _id = prof["_id"]
    else:
        # Verifica se o professor existe
        prof = mongo.db.professores.find_one({"_id": _id})
        if not prof:
            return jsonify({"error": "not_found", "msg": "Professor não encontrado"}), 404

    # Verifica se o usuário é do tipo professor (aceita "professor" ou "prof")
    claims = get_jwt() or {}
    user_tipo = claims.get("tipo", "").lower()
    if user_tipo not in ["professor", "prof"]:
        return jsonify({"error": "forbidden", "msg": "Acesso permitido apenas para professores"}), 403

    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in PROF_FIELDS and k not in {"email", "saldo"}}

    # normaliza listas (inclui idiomas)
    for f in ("especializacoes", "quer_ensinar", "skills", "modalidades", "idiomas"):
        if f in body:
            body[f] = normalize_list_maybe(body.get(f))

    # converte valor_hora para número (valor cobrado pelo professor)
    if "valor_hora" in body:
        vh = maybe_number(body.get("valor_hora"))
        if vh is None:
            body.pop("valor_hora", None)
        else:
            body["valor_hora"] = vh

    # slug updates
    doc_atual = mongo.db.professores.find_one({"_id": _id}, {"nome": 1, "slug": 1})
    if "slug" in body and body["slug"]:
        base = slugify(body["slug"])
        new_slug = base
        exists = mongo.db.professores.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    elif "nome" in body:
        base = slugify(body["nome"])
        new_slug = base
        exists = mongo.db.professores.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    elif doc_atual and not doc_atual.get("slug") and doc_atual.get("nome"):
        base = slugify(doc_atual["nome"])
        new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug

    # senha -> senha_hash
    if "senha" in body:
        nova = body.pop("senha")
        if nova:
            body["senha_hash"] = hash_password(nova)

    if not body:
        return jsonify({"error": "no_fields_to_update"}), 400

    body["updated_at"] = now()
    r = mongo.db.professores.update_one({"_id": _id}, {"$set": body})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404

    doc = mongo.db.professores.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))


@bp.put("/<id>")
@jwt_required()
def update(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in PROF_FIELDS and k not in {"email", "saldo"}}

    # normaliza listas (inclui idiomas)
    for f in ("especializacoes", "quer_ensinar", "skills", "modalidades", "idiomas"):
        if f in body:
            body[f] = normalize_list_maybe(body.get(f))

    # valor_hora -> número
    if "valor_hora" in body:
        vh = maybe_number(body.get("valor_hora"))
        if vh is None:
            body.pop("valor_hora", None)
        else:
            body["valor_hora"] = vh

    # slug handling
    doc_atual = mongo.db.professores.find_one({"_id": _id}, {"nome": 1, "slug": 1})
    if "slug" in body and body["slug"]:
        base = slugify(body["slug"])
        new_slug = base
        exists = mongo.db.professores.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    elif "nome" in body:
        base = slugify(body["nome"])
        new_slug = base
        exists = mongo.db.professores.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    elif doc_atual and not doc_atual.get("slug") and doc_atual.get("nome"):
        base = slugify(doc_atual["nome"])
        new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug

    # senha -> senha_hash
    if "senha" in body:
        nova = body.pop("senha")
        if nova:
            body["senha_hash"] = hash_password(nova)

    if not body:
        return jsonify({"error": "no_fields_to_update"}), 400

    body["updated_at"] = now()
    r = mongo.db.professores.update_one({"_id": _id}, {"$set": body})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404

    doc = mongo.db.professores.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))


@bp.delete("/<id>")
@jwt_required()
def delete(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    r = mongo.db.professores.delete_one({"_id": _id})
    return ("", 204) if r.deleted_count else (jsonify({"error": "not_found"}), 404)


# ----------- Perfil público por slug (sem JWT) -----------
@bp.route("/slug/<slug>", methods=["GET"])
@bp.route("/slug/<slug>/", methods=["GET"])   # aceita a barra final também
def get_public_by_slug(slug):
    # Primeiro tenta buscar pelo slug exato
    doc = mongo.db.professores.find_one({"slug": slug, "visibilidade": {"$ne": "privado"}}, {})

    # Se não encontrou pelo slug, tenta buscar professores sem slug e comparar normalizado
    if not doc:
        palavras_slug = [p for p in slug.replace("-", " ").split() if p]
        if palavras_slug:
            regex_pattern = ".*".join(palavras_slug)
            doc = mongo.db.professores.find_one({
                "nome": {"$regex": regex_pattern, "$options": "i"},
                "visibilidade": {"$ne": "privado"}
            }, {})

        if not doc:
            todos_sem_slug = list(mongo.db.professores.find(
                {"visibilidade": {"$ne": "privado"}, "$or": [{"slug": {"$exists": False}}, {"slug": None}, {"slug": ""}]},
                {"nome": 1, "_id": 1}
            ).limit(100))

            slug_normalized = slugify(slug).lower()
            for prof in todos_sem_slug:
                nome_normalized = slugify(prof.get("nome", "")).lower()
                if nome_normalized == slug_normalized:
                    doc = mongo.db.professores.find_one({"_id": prof["_id"]}, {})
                    break

    if not doc:
        return jsonify({"error": "not_found"}), 404

    # Se encontrou mas não tem slug, criar um baseado no nome
    if not doc.get("slug") and doc.get("nome"):
        novo_slug = ensure_unique_slug(slugify(doc["nome"]))
        mongo.db.professores.update_one({"_id": doc["_id"]}, {"$set": {"slug": novo_slug}})
        doc["slug"] = novo_slug

    safe = scrub(doc)
    safe.pop("cpf", None); safe.pop("telefone", None); safe.pop("email", None)
    return jsonify(safe)
