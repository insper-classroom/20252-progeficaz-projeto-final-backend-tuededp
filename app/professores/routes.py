from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from pymongo.errors import DuplicateKeyError
from ..extensions import mongo
from ..utils import oid, now, scrub, hash_password

bp = Blueprint("professores", __name__)

PROF_FIELDS = {
    "nome","telefone","cpf","email","senha","saldo",
    "bio","historico_academico_profissional",
    "data_nascimento",
    "endereco"
}

@bp.post("/")
def create():
    data = request.get_json(force=True) or {}
    body = {k:v for k,v in data.items() if k in PROF_FIELDS}
    if not body.get("nome") or not body.get("email"):
        return jsonify({"error":"missing_fields","required":["nome","email"]}), 400

    body["email"] = body["email"].strip().lower()
    body.setdefault("saldo", 0.0)

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

@bp.put("/<id>")
@jwt_required()
def update(id):
    _id = oid(id)
    if not _id: return jsonify({"error":"invalid_id"}), 400
    data = request.get_json(force=True) or {}
    body = {k:v for k,v in data.items() if k in PROF_FIELDS and k not in {"email","saldo"}}

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

