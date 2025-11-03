from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from pymongo.errors import DuplicateKeyError
import re
from ..extensions import mongo
from ..utils import oid, now, scrub, hash_password

bp = Blueprint("professores", __name__)

PROF_FIELDS = {
    "nome","telefone","cpf","email","senha","saldo",
    "bio","historico_academico_profissional",
    "data_nascimento",
    "endereco", "slug", "visibilidade"
    "area"  
}

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

@bp.post("/")
def create():
    data = request.get_json(force=True) or {}
    body = {k:v for k,v in data.items() if k in PROF_FIELDS}
    if not body.get("nome") or not body.get("email"):
        return jsonify({"error":"missing_fields","required":["nome","email"]}), 400

    body["email"] = body["email"].strip().lower()
    body.setdefault("saldo", 0.0)
    body.setdefault("visibilidade", "publico")

    # Garantir slug único
    if not body.get("slug"):
        base = slugify(body.get("nome"))
        body["slug"] = ensure_unique_slug(base)

    senha = body.pop("senha", None)
    if senha:
        body["senha_hash"] = hash_password(senha)
    if "senha" in body:
        nova = body.pop("senha")
        if nova:
            body["senha_hash"] = hash_password(nova)
    
    body["created_at"] = body["updated_at"] = now()

    try:
        res = mongo.db.professores.insert_one(body)
    except DuplicateKeyError:
        return jsonify({"error":"email_already_exists"}), 409

    doc = mongo.db.professores.find_one({"_id": res.inserted_id}, {})
    return jsonify(scrub(doc)), 201

@bp.get("/")
def list_():
    q = request.args.get("q")
    cidade = request.args.get("cidade")
    estado = request.args.get("estado")
    area = request.args.get("area")
    page = int(request.args.get("page", 1)); limit = int(request.args.get("limit", 10))
    order = int(request.args.get("order", -1)); sort = request.args.get("sort", "created_at")

    filt = {}
    if q:
        filt["$or"] = [
            {"nome": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"bio": {"$regex": q, "$options": "i"}},
            {"historico_academico_profissional": {"$regex": q, "$options": "i"}},
        ]
    if cidade: filt["endereco.cidade"] = {"$regex": f"^{cidade}$", "$options":"i"}
    if estado: filt["endereco.estado"] = {"$regex": f"^{estado}$", "$options":"i"}
    if area:
        filt["area"] = {"$regex": f"^{area}$", "$options":"i"}

    cur = (mongo.db.professores.find(filt, {})
           .sort(sort, order)
           .skip((page-1)*limit)
           .limit(limit))
    total = mongo.db.professores.count_documents(filt)
    return jsonify({"data":[scrub(d) for d in cur], "total":total, "page":page, "limit":limit})

@bp.get("/<id>")
def get_(id):
    _id = oid(id)
    if not _id: return jsonify({"error":"invalid_id"}), 400
    doc = mongo.db.professores.find_one({"_id": _id}, {})
    if not doc: return jsonify({"error":"not_found"}), 404
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
        # Se não conseguiu converter para ObjectId, pode ser que o ID está em formato string diferente
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
    body = {k:v for k,v in data.items() if k in PROF_FIELDS and k not in {"email","saldo"}}
    
    # Atualizar slug se o nome mudou, se slug foi fornecido, ou se não tem slug
    doc_atual = mongo.db.professores.find_one({"_id": _id}, {"nome": 1, "slug": 1})
    
    if "slug" in body and body["slug"]:
        # Slug fornecido explicitamente
        base = slugify(body["slug"])
        new_slug = base
        exists = mongo.db.professores.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    elif "nome" in body:
        # Nome mudou, atualizar slug baseado no novo nome
        base = slugify(body["nome"])
        new_slug = base
        exists = mongo.db.professores.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    elif doc_atual and not doc_atual.get("slug") and doc_atual.get("nome"):
        # Não tem slug, criar um baseado no nome atual
        base = slugify(doc_atual["nome"])
        new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    
    if "senha" in body:
        nova = body.pop("senha")
        try:
            import bcrypt
            if nova: body["senha_hash"] = bcrypt.hashpw(nova.encode(), bcrypt.gensalt()).decode()
        except Exception:
            pass
    
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
    if not _id: return jsonify({"error":"invalid_id"}), 400
    data = request.get_json(force=True) or {}
    body = {k:v for k,v in data.items() if k in PROF_FIELDS and k not in {"email","saldo"}}

    # Atualizar slug se o nome mudou, se slug foi fornecido, ou se não tem slug
    doc_atual = mongo.db.professores.find_one({"_id": _id}, {"nome": 1, "slug": 1})
    
    if "slug" in body and body["slug"]:
        # Slug fornecido explicitamente
        base = slugify(body["slug"])
        new_slug = base
        exists = mongo.db.professores.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    elif "nome" in body:
        # Nome mudou, atualizar slug baseado no novo nome
        base = slugify(body["nome"])
        new_slug = base
        exists = mongo.db.professores.find_one({"slug": new_slug, "_id": {"$ne": _id}}, {"_id": 1})
        if exists:
            new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug
    elif doc_atual and not doc_atual.get("slug") and doc_atual.get("nome"):
        # Não tem slug, criar um baseado no nome atual
        base = slugify(doc_atual["nome"])
        new_slug = ensure_unique_slug(base)
        body["slug"] = new_slug

    if "senha" in body:
        nova = body.pop("senha")
        try:
            import bcrypt
            if nova: body["senha_hash"] = bcrypt.hashpw(nova.encode(), bcrypt.gensalt()).decode()
        except Exception:
            pass
            
    if not body: return jsonify({"error":"no_fields_to_update"}), 400
    body["updated_at"] = now()
    r = mongo.db.professores.update_one({"_id": _id}, {"$set": body})
    if r.matched_count == 0: return jsonify({"error":"not_found"}), 404
    doc = mongo.db.professores.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))

@bp.delete("/<id>")
@jwt_required()
def delete(id):
    _id = oid(id)
    if not _id: return jsonify({"error":"invalid_id"}), 400
    r = mongo.db.professores.delete_one({"_id": _id})
    return ("",204) if r.deleted_count else (jsonify({"error":"not_found"}),404)

# ----------- Perfil público por slug (sem JWT) -----------
@bp.route("/slug/<slug>", methods=["GET"])
@bp.route("/slug/<slug>/", methods=["GET"])   # aceita a barra final também
def get_public_by_slug(slug):
    # Primeiro tenta buscar pelo slug exato
    doc = mongo.db.professores.find_one({"slug": slug, "visibilidade": {"$ne": "privado"}}, {})
    
    # Se não encontrou pelo slug, tenta buscar professores sem slug e comparar normalizado
    # (para professores antigos que não têm slug no banco)
    if not doc:
        # Converte slug para padrão de busca no nome (remove hífens, busca por palavras)
        palavras_slug = [p for p in slug.replace("-", " ").split() if p]
        if palavras_slug:
            # Busca professores que tenham essas palavras no nome
            regex_pattern = ".*".join(palavras_slug)
            doc = mongo.db.professores.find_one({
                "nome": {"$regex": regex_pattern, "$options": "i"},
                "visibilidade": {"$ne": "privado"}
            }, {})
        
        # Se ainda não encontrou, busca todos os públicos sem slug e compara normalizado
        if not doc:
            todos_sem_slug = list(mongo.db.professores.find(
                {"visibilidade": {"$ne": "privado"}, "$or": [{"slug": {"$exists": False}}, {"slug": None}, {"slug": ""}]},
                {"nome": 1, "_id": 1}
            ).limit(100))  # Limite para não sobrecarregar
            
            slug_normalized = slugify(slug).lower()
            for prof in todos_sem_slug:
                nome_normalized = slugify(prof.get("nome", "")).lower()
                if nome_normalized == slug_normalized:
                    doc = mongo.db.professores.find_one({"_id": prof["_id"]}, {})
                    break
    
    if not doc: 
        return jsonify({"error":"not_found"}), 404
    
    # Se encontrou mas não tem slug, criar um baseado no nome
    if not doc.get("slug") and doc.get("nome"):
        novo_slug = ensure_unique_slug(slugify(doc["nome"]))
        mongo.db.professores.update_one({"_id": doc["_id"]}, {"$set": {"slug": novo_slug}})
        doc["slug"] = novo_slug
    
    safe = scrub(doc)
    safe.pop("cpf", None); safe.pop("telefone", None); safe.pop("email", None)
    return jsonify(safe)

# ----------- Professores em alta (melhores avaliações) -----------
@bp.route("/destaque", methods=["OPTIONS"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def destaque_options():
    return ("", 204)

@bp.route("/destaque", methods=["GET"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def get_em_alta():
    """Retorna professores com melhores avaliações (em alta)."""
    try:
        limit = int(request.args.get("limit", 6))
        
        # Verificar se há avaliações no banco
        total_avaliacoes = mongo.db.avaliacoes.count_documents({})
        print(f"[PROFESSORES DESTAQUE] Total de avaliações no banco: {total_avaliacoes}")
        
        if total_avaliacoes == 0:
            # Se não há avaliações, retornar professores aleatórios ou vazio
            return jsonify({"data": [], "total": 0}), 200
        
        # Pipeline de agregação para calcular nota média por professor
        # Primeiro, filtrar apenas avaliações com id_prof válido
        pipeline = [
            {
                "$match": {
                    "id_prof": {"$exists": True, "$ne": None}  # Só avaliações com id_prof válido
                }
            },
            {
                "$group": {
                    "_id": "$id_prof",
                    "nota_media": {"$avg": "$nota"},
                    "total_avaliacoes": {"$sum": 1}
                }
            },
            {
                "$match": {
                    "total_avaliacoes": {"$gte": 1},  # Pelo menos 1 avaliação
                    "nota_media": {"$gte": 4.0}  # Nota média mínima de 4.0
                }
            },
            {
                "$sort": {"nota_media": -1, "total_avaliacoes": -1}  # Ordena por nota média e quantidade
            },
            {
                "$limit": limit
            }
        ]
        
        try:
            avaliacoes_agregadas = list(mongo.db.avaliacoes.aggregate(pipeline))
            print(f"[PROFESSORES DESTAQUE] Avaliações agregadas: {len(avaliacoes_agregadas)}")
        except Exception as agg_error:
            print(f"[PROFESSORES DESTAQUE] Erro na agregação: {str(agg_error)}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": "aggregation_error", "details": str(agg_error)}), 500
        
        # Buscar dados dos professores
        professores_em_alta = []
        for item in avaliacoes_agregadas:
            prof_id = item.get("_id")
            if not prof_id:
                print(f"[PROFESSORES DESTAQUE] Item sem _id: {item}")
                continue
            
            # Converter para ObjectId se necessário
            try:
                from bson import ObjectId
                if isinstance(prof_id, str):
                    prof_id = ObjectId(prof_id)
                elif not isinstance(prof_id, ObjectId):
                    print(f"[PROFESSORES DESTAQUE] ID inválido: {prof_id}, tipo: {type(prof_id)}")
                    continue
            except Exception as oid_error:
                print(f"[PROFESSORES DESTAQUE] Erro ao converter ObjectId: {str(oid_error)}")
                continue
            
            prof = mongo.db.professores.find_one({"_id": prof_id}, {"senha_hash": 0, "cpf": 0, "telefone": 0})
            
            if prof and prof.get("visibilidade") != "privado":
                prof_doc = scrub(prof)
                prof_doc["nota_media"] = round(item["nota_media"], 1)
                prof_doc["total_avaliacoes"] = item["total_avaliacoes"]
                professores_em_alta.append(prof_doc)
        
        print(f"[PROFESSORES DESTAQUE] Professores em alta encontrados: {len(professores_em_alta)}")
        return jsonify({"data": professores_em_alta, "total": len(professores_em_alta)}), 200
    except Exception as e:
        print(f"[PROFESSORES DESTAQUE] ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "stats_error", "details": str(e)}), 500
