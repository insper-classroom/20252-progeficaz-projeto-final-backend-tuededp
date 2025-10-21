from flask import Blueprint, request, jsonify
from pymongo.errors import DuplicateKeyError
from ..extensions import mongo
from ..utils import oid, now, scrub

bp = Blueprint("categorias", __name__)

CATEGORIA_FIELDS = {"nome"}

@bp.post("/")
def create():
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in CATEGORIA_FIELDS}
    
    if not body.get("nome"):
        return jsonify({"error": "missing_fields", "required": ["nome"]}), 400
    
    body["nome"] = body["nome"].strip()
    if not body["nome"]:
        return jsonify({"error": "nome_cannot_be_empty"}), 400
    
    body["created_at"] = body["updated_at"] = now()
    
    try:
        res = mongo.db.categorias.insert_one(body)
    except DuplicateKeyError:
        return jsonify({"error": "categoria_already_exists"}), 409
    except Exception as e:
        return jsonify({"error": "creation_failed", "details": str(e)}), 500
    
    doc = mongo.db.categorias.find_one({"_id": res.inserted_id}, {})
    return jsonify(scrub(doc)), 201

@bp.get("/")
def list_():
    q = request.args.get("q")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    order = int(request.args.get("order", -1))
    sort = request.args.get("sort", "created_at")
    
    filt = {}
    if q:
        filt["nome"] = {"$regex": q, "$options": "i"}
    
    cur = (mongo.db.categorias.find(filt, {})
           .sort(sort, order)
           .skip((page-1)*limit)
           .limit(limit))
    total = mongo.db.categorias.count_documents(filt)
    
    # Enriquecer com contagem de aulas por categoria
    categorias = []
    for cat in cur:
        cat_doc = scrub(cat)
        # Contar aulas nesta categoria
        aulas_count = mongo.db.aulas.count_documents({"id_categoria": cat["_id"]})
        cat_doc["aulas_count"] = aulas_count
        categorias.append(cat_doc)
    
    return jsonify({"data": categorias, "total": total, "page": page, "limit": limit})

@bp.get("/<id>")
def get_(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    doc = mongo.db.categorias.find_one({"_id": _id}, {})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    
    cat_doc = scrub(doc)
    
    # Enriquecer com contagem de aulas
    aulas_count = mongo.db.aulas.count_documents({"id_categoria": _id})
    cat_doc["aulas_count"] = aulas_count
    
    # Buscar algumas aulas desta categoria
    aulas = mongo.db.aulas.find(
        {"id_categoria": _id}, 
        {"titulo": 1, "preco_decimal": 1, "status": 1, "created_at": 1}
    ).limit(5)
    
    cat_doc["aulas"] = [scrub(aula) for aula in aulas]
    
    return jsonify(cat_doc)

@bp.put("/<id>")
def update(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in CATEGORIA_FIELDS}
    
    if not body:
        return jsonify({"error": "no_fields_to_update"}), 400
    
    if "nome" in body:
        body["nome"] = body["nome"].strip()
        if not body["nome"]:
            return jsonify({"error": "nome_cannot_be_empty"}), 400
    
    body["updated_at"] = now()
    
    r = mongo.db.categorias.update_one({"_id": _id}, {"$set": body})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404
    
    doc = mongo.db.categorias.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))

@bp.delete("/<id>")
def delete(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    # Verificar se há aulas usando esta categoria
    aulas_count = mongo.db.aulas.count_documents({"id_categoria": _id})
    if aulas_count > 0:
        return jsonify({
            "error": "categoria_in_use", 
            "message": f"Categoria está sendo usada por {aulas_count} aula(s). Remova as aulas primeiro."
        }), 409
    
    r = mongo.db.categorias.delete_one({"_id": _id})
    return ("", 204) if r.deleted_count else (jsonify({"error": "not_found"}), 404)

@bp.get("/<id>/aulas")
def get_aulas_by_categoria(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    # Verificar se a categoria existe
    categoria = mongo.db.categorias.find_one({"_id": _id})
    if not categoria:
        return jsonify({"error": "categoria_not_found"}), 404
    
    q = request.args.get("q")
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    order = int(request.args.get("order", -1))
    sort = request.args.get("sort", "created_at")
    
    filt = {"id_categoria": _id}
    
    if q:
        filt["$or"] = [
            {"titulo": {"$regex": q, "$options": "i"}},
            {"descricao_aula": {"$regex": q, "$options": "i"}},
        ]
    if status:
        filt["status"] = status
    
    cur = (mongo.db.aulas.find(filt, {})
           .sort(sort, order)
           .skip((page-1)*limit)
           .limit(limit))
    total = mongo.db.aulas.count_documents(filt)
    
    # Enriquecer dados com informações do professor
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
        
        aulas.append(aula_doc)
    
    return jsonify({
        "categoria": scrub(categoria),
        "data": aulas, 
        "total": total, 
        "page": page, 
        "limit": limit
    })