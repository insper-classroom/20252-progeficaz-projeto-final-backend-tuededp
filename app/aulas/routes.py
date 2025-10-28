from flask import Blueprint, request, jsonify
from pymongo.errors import DuplicateKeyError
from ..extensions import mongo
from ..utils import oid, now, scrub
from flask import current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os, time


bp = Blueprint("aulas", __name__)

AULA_FIELDS = {
    "titulo", "descricao_aula", "preco_decimal", "id_categoria", "id_professor"
}

@bp.post("/")
def create():
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in AULA_FIELDS}
    
    if not body.get("titulo") or not body.get("id_professor"):
        return jsonify({"error": "missing_fields", "required": ["titulo", "id_professor"]}), 400
    
    # Validar se o professor existe
    prof_id = oid(body.get("id_professor"))
    if not prof_id:
        return jsonify({"error": "invalid_professor_id"}), 400
    
    professor = mongo.db.professores.find_one({"_id": prof_id})
    if not professor:
        return jsonify({"error": "professor_not_found"}), 404
    
    # Validar se a categoria existe (se fornecida)
    if body.get("id_categoria"):
        cat_id = oid(body.get("id_categoria"))
        if not cat_id:
            return jsonify({"error": "invalid_category_id"}), 400
        
        categoria = mongo.db.categorias.find_one({"_id": cat_id})
        if not categoria:
            return jsonify({"error": "category_not_found"}), 404
    
    # Converter preço para decimal
    if body.get("preco_decimal"):
        try:
            body["preco_decimal"] = float(body["preco_decimal"])
        except (ValueError, TypeError):
            return jsonify({"error": "invalid_price_format"}), 400
    
    body["created_at"] = body["updated_at"] = now()
    body["status"] = "disponivel"  # Status padrão
    
    try:
        res = mongo.db.aulas.insert_one(body)
    except Exception as e:
        return jsonify({"error": "creation_failed", "details": str(e)}), 500
    
    doc = mongo.db.aulas.find_one({"_id": res.inserted_id}, {})
    return jsonify(scrub(doc)), 201

@bp.get("/")
def list_():
    q = request.args.get("q")
    categoria = request.args.get("categoria")
    professor = request.args.get("professor")
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    order = int(request.args.get("order", -1))
    sort = request.args.get("sort", "created_at")
    
    filt = {}
    if q:
        filt["$or"] = [
            {"titulo": {"$regex": q, "$options": "i"}},
            {"descricao_aula": {"$regex": q, "$options": "i"}},
        ]
    if categoria:
        cat_id = oid(categoria)
        if cat_id:
            filt["id_categoria"] = cat_id
    if professor:
        prof_id = oid(professor)
        if prof_id:
            filt["id_professor"] = prof_id
    if status:
        filt["status"] = status
    
    cur = (mongo.db.aulas.find(filt, {})
           .sort(sort, order)
           .skip((page-1)*limit)
           .limit(limit))
    total = mongo.db.aulas.count_documents(filt)
    
    # Enriquecer dados com informações do professor e categoria
    aulas = []
    for aula in cur:
        aula_doc = scrub(aula)
        
        # Buscar dados do professor
        if aula.get("id_professor"):
            prof = mongo.db.professores.find_one({"_id": aula["id_professor"]}, {"nome": 1, "email": 1, "bio": 1})
            if prof:
                aula_doc["professor"] = {
                    "id": str(prof["_id"]),
                    "nome": prof.get("nome"),
                    "email": prof.get("email"),
                    "bio": prof.get("bio")
                }
        
        # Buscar dados da categoria
        if aula.get("id_categoria"):
            cat = mongo.db.categorias.find_one({"_id": aula["id_categoria"]}, {"nome": 1})
            if cat:
                aula_doc["categoria"] = {
                    "id": str(cat["_id"]),
                    "nome": cat.get("nome")
                }
        
        aulas.append(aula_doc)
    
    return jsonify({"data": aulas, "total": total, "page": page, "limit": limit})

@bp.get("/<id>")
def get_(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    doc = mongo.db.aulas.find_one({"_id": _id}, {})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    
    aula_doc = scrub(doc)
    
    # Enriquecer com dados do professor
    if doc.get("id_professor"):
        prof = mongo.db.professores.find_one({"_id": doc["id_professor"]}, {"nome": 1, "email": 1, "bio": 1, "historico_academico_profissional": 1})
        if prof:
            aula_doc["professor"] = {
                "id": str(prof["_id"]),
                "nome": prof.get("nome"),
                "email": prof.get("email"),
                "bio": prof.get("bio"),
                "historico_academico_profissional": prof.get("historico_academico_profissional")
            }
    
    # Enriquecer com dados da categoria
    if doc.get("id_categoria"):
        cat = mongo.db.categorias.find_one({"_id": doc["id_categoria"]}, {"nome": 1})
        if cat:
            aula_doc["categoria"] = {
                "id": str(cat["_id"]),
                "nome": cat.get("nome")
            }
    
    return jsonify(aula_doc)

@bp.put("/<id>")
def update(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in AULA_FIELDS}
    
    # Validar professor se fornecido
    if body.get("id_professor"):
        prof_id = oid(body.get("id_professor"))
        if not prof_id:
            return jsonify({"error": "invalid_professor_id"}), 400
        
        professor = mongo.db.professores.find_one({"_id": prof_id})
        if not professor:
            return jsonify({"error": "professor_not_found"}), 404
    
    # Validar categoria se fornecida
    if body.get("id_categoria"):
        cat_id = oid(body.get("id_categoria"))
        if not cat_id:
            return jsonify({"error": "invalid_category_id"}), 400
        
        categoria = mongo.db.categorias.find_one({"_id": cat_id})
        if not categoria:
            return jsonify({"error": "category_not_found"}), 404
    
    # Converter preço para decimal
    if body.get("preco_decimal"):
        try:
            body["preco_decimal"] = float(body["preco_decimal"])
        except (ValueError, TypeError):
            return jsonify({"error": "invalid_price_format"}), 400
    
    if not body:
        return jsonify({"error": "no_fields_to_update"}), 400
    
    body["updated_at"] = now()
    
    r = mongo.db.aulas.update_one({"_id": _id}, {"$set": body})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404
    
    doc = mongo.db.aulas.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))

@bp.delete("/<id>")
def delete(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    r = mongo.db.aulas.delete_one({"_id": _id})
    return ("", 204) if r.deleted_count else (jsonify({"error": "not_found"}), 404)

@bp.put("/<id>/status")
def update_status(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    data = request.get_json(force=True) or {}
    novo_status = data.get("status")
    
    if not novo_status:
        return jsonify({"error": "missing_status"}), 400
    
    # Validar status
    status_validos = ["disponivel", "em andamento", "cancelada", "concluida"]
    if novo_status not in status_validos:
        return jsonify({"error": "invalid_status", "valid_statuses": status_validos}), 400
    
    # Atualizar status da aula
    r = mongo.db.aulas.update_one({"_id": _id}, {"$set": {"status": novo_status, "updated_at": now()}})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404
    
    # Registrar mudança de status
    status_doc = {
        "id_aula": _id,
        "novo_status": novo_status,
        "data_hora": now(),
        "created_at": now()
    }
    
    # Se tiver professor na requisição, adicionar
    if data.get("id_professor"):
        prof_id = oid(data.get("id_professor"))
        if prof_id:
            status_doc["id_professor"] = prof_id
    
    mongo.db.status_aulas.insert_one(status_doc)
    
    doc = mongo.db.aulas.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))
