from flask import Blueprint, request, jsonify
from pymongo.errors import DuplicateKeyError
from ..extensions import mongo
from ..utils import oid, now, scrub

bp = Blueprint("avaliacoes", __name__)

AVALIACAO_FIELDS = {"id_aluno", "id_aula", "id_prof", "nota", "texto"}

@bp.post("/")
def create():
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in AVALIACAO_FIELDS}
    
    required_fields = ["id_aluno", "id_aula", "id_prof", "nota"]
    if not all(body.get(field) for field in required_fields):
        return jsonify({"error": "missing_fields", "required": required_fields}), 400
    
    # Validar se aluno existe
    aluno_id = oid(body.get("id_aluno"))
    if not aluno_id:
        return jsonify({"error": "invalid_aluno_id"}), 400
    
    aluno = mongo.db.alunos.find_one({"_id": aluno_id})
    if not aluno:
        return jsonify({"error": "aluno_not_found"}), 404
    
    # Validar se professor existe
    prof_id = oid(body.get("id_prof"))
    if not prof_id:
        return jsonify({"error": "invalid_professor_id"}), 400
    
    professor = mongo.db.professores.find_one({"_id": prof_id})
    if not professor:
        return jsonify({"error": "professor_not_found"}), 404
    
    # Validar se aula existe
    aula_id = oid(body.get("id_aula"))
    if not aula_id:
        return jsonify({"error": "invalid_aula_id"}), 400
    
    aula = mongo.db.aulas.find_one({"_id": aula_id})
    if not aula:
        return jsonify({"error": "aula_not_found"}), 404
    
    # Validar se a aula pertence ao professor
    if aula.get("id_professor") != prof_id:
        return jsonify({"error": "aula_does_not_belong_to_professor"}), 400
    
    # Validar nota
    try:
        nota = float(body.get("nota"))
        if not (0 <= nota <= 10):
            return jsonify({"error": "invalid_nota_range", "message": "Nota deve estar entre 0 e 10"}), 400
        body["nota"] = nota
    except (ValueError, TypeError):
        return jsonify({"error": "invalid_nota_format"}), 400
    
    # Verificar se já existe avaliação do mesmo aluno para a mesma aula
    existing = mongo.db.avaliacoes.find_one({
        "id_aluno": aluno_id,
        "id_aula": aula_id
    })
    if existing:
        return jsonify({"error": "avaliacao_already_exists", "message": "Aluno já avaliou esta aula"}), 409
    
    # Verificar se o aluno realmente participou da aula (tem agendamento concluído)
    agendamento = mongo.db.agenda.find_one({
        "id_aluno": aluno_id,
        "id_aula": aula_id,
        "id_professor": prof_id,
        "status": "concluida"
    })
    if not agendamento:
        return jsonify({"error": "aluno_did_not_attend_class", "message": "Aluno deve ter participado da aula para avaliar"}), 400
    
    body["created_at"] = body["updated_at"] = now()
    
    try:
        res = mongo.db.avaliacoes.insert_one(body)
    except Exception as e:
        return jsonify({"error": "creation_failed", "details": str(e)}), 500
    
    doc = mongo.db.avaliacoes.find_one({"_id": res.inserted_id}, {})
    return jsonify(scrub(doc)), 201

@bp.get("/")
def list_():
    aluno = request.args.get("aluno")
    professor = request.args.get("professor")
    aula = request.args.get("aula")
    nota_min = request.args.get("nota_min")
    nota_max = request.args.get("nota_max")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    order = int(request.args.get("order", -1))
    sort = request.args.get("sort", "created_at")
    
    filt = {}
    
    if aluno:
        aluno_id = oid(aluno)
        if aluno_id:
            filt["id_aluno"] = aluno_id
    
    if professor:
        prof_id = oid(professor)
        if prof_id:
            filt["id_prof"] = prof_id
    
    if aula:
        aula_id = oid(aula)
        if aula_id:
            filt["id_aula"] = aula_id
    
    # Filtro por faixa de nota
    if nota_min or nota_max:
        nota_filtro = {}
        if nota_min:
            try:
                nota_filtro["$gte"] = float(nota_min)
            except (ValueError, TypeError):
                return jsonify({"error": "invalid_nota_min_format"}), 400
        if nota_max:
            try:
                nota_filtro["$lte"] = float(nota_max)
            except (ValueError, TypeError):
                return jsonify({"error": "invalid_nota_max_format"}), 400
        filt["nota"] = nota_filtro
    
    cur = (mongo.db.avaliacoes.find(filt, {})
           .sort(sort, order)
           .skip((page-1)*limit)
           .limit(limit))
    total = mongo.db.avaliacoes.count_documents(filt)
    
    # Enriquecer dados
    avaliacoes = []
    for avaliacao in cur:
        avaliacao_doc = scrub(avaliacao)
        
        # Buscar dados do aluno
        if avaliacao.get("id_aluno"):
            aluno = mongo.db.alunos.find_one({"_id": avaliacao["id_aluno"]}, {"nome": 1, "email": 1})
            if aluno:
                avaliacao_doc["aluno"] = {
                    "id": str(aluno["_id"]),
                    "nome": aluno.get("nome"),
                    "email": aluno.get("email")
                }
        
        # Buscar dados do professor
        if avaliacao.get("id_prof"):
            prof = mongo.db.professores.find_one({"_id": avaliacao["id_prof"]}, {"nome": 1, "email": 1})
            if prof:
                avaliacao_doc["professor"] = {
                    "id": str(prof["_id"]),
                    "nome": prof.get("nome"),
                    "email": prof.get("email")
                }
        
        # Buscar dados da aula
        if avaliacao.get("id_aula"):
            aula = mongo.db.aulas.find_one({"_id": avaliacao["id_aula"]}, {"titulo": 1, "descricao_aula": 1})
            if aula:
                avaliacao_doc["aula"] = {
                    "id": str(aula["_id"]),
                    "titulo": aula.get("titulo"),
                    "descricao_aula": aula.get("descricao_aula")
                }
        
        avaliacoes.append(avaliacao_doc)
    
    return jsonify({"data": avaliacoes, "total": total, "page": page, "limit": limit})

@bp.get("/<id>")
def get_(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    doc = mongo.db.avaliacoes.find_one({"_id": _id}, {})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    
    avaliacao_doc = scrub(doc)
    
    # Enriquecer com dados completos
    if doc.get("id_aluno"):
        aluno = mongo.db.alunos.find_one({"_id": doc["id_aluno"]})
        if aluno:
            avaliacao_doc["aluno"] = scrub(aluno)
    
    if doc.get("id_prof"):
        prof = mongo.db.professores.find_one({"_id": doc["id_prof"]})
        if prof:
            avaliacao_doc["professor"] = scrub(prof)
    
    if doc.get("id_aula"):
        aula = mongo.db.aulas.find_one({"_id": doc["id_aula"]})
        if aula:
            avaliacao_doc["aula"] = scrub(aula)
    
    return jsonify(avaliacao_doc)

@bp.put("/<id>")
def update(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in AVALIACAO_FIELDS}
    
    # Validar nota se fornecida
    if body.get("nota"):
        try:
            nota = float(body.get("nota"))
            if not (0 <= nota <= 10):
                return jsonify({"error": "invalid_nota_range", "message": "Nota deve estar entre 0 e 10"}), 400
            body["nota"] = nota
        except (ValueError, TypeError):
            return jsonify({"error": "invalid_nota_format"}), 400
    
    if not body:
        return jsonify({"error": "no_fields_to_update"}), 400
    
    body["updated_at"] = now()
    
    r = mongo.db.avaliacoes.update_one({"_id": _id}, {"$set": body})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404
    
    doc = mongo.db.avaliacoes.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))

@bp.delete("/<id>")
def delete(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    r = mongo.db.avaliacoes.delete_one({"_id": _id})
    return ("", 204) if r.deleted_count else (jsonify({"error": "not_found"}), 404)

@bp.get("/professor/<professor_id>/stats")
def get_professor_stats(professor_id):
    prof_id = oid(professor_id)
    if not prof_id:
        return jsonify({"error": "invalid_professor_id"}), 400
    
    # Verificar se professor existe
    professor = mongo.db.professores.find_one({"_id": prof_id})
    if not professor:
        return jsonify({"error": "professor_not_found"}), 404
    
    # Calcular estatísticas
    pipeline = [
        {"$match": {"id_prof": prof_id}},
        {"$group": {
            "_id": None,
            "total_avaliacoes": {"$sum": 1},
            "nota_media": {"$avg": "$nota"},
            "nota_min": {"$min": "$nota"},
            "nota_max": {"$max": "$nota"}
        }}
    ]
    
    stats = list(mongo.db.avaliacoes.aggregate(pipeline))
    
    if not stats:
        return jsonify({
            "professor": scrub(professor),
            "total_avaliacoes": 0,
            "nota_media": 0,
            "nota_min": 0,
            "nota_max": 0
        })
    
    result = stats[0]
    result.pop("_id", None)
    result["professor"] = scrub(professor)
    
    return jsonify(result)

@bp.get("/aula/<aula_id>/stats")
def get_aula_stats(aula_id):
    aula_obj_id = oid(aula_id)
    if not aula_obj_id:
        return jsonify({"error": "invalid_aula_id"}), 400
    
    # Verificar se aula existe
    aula = mongo.db.aulas.find_one({"_id": aula_obj_id})
    if not aula:
        return jsonify({"error": "aula_not_found"}), 404
    
    # Calcular estatísticas
    pipeline = [
        {"$match": {"id_aula": aula_obj_id}},
        {"$group": {
            "_id": None,
            "total_avaliacoes": {"$sum": 1},
            "nota_media": {"$avg": "$nota"},
            "nota_min": {"$min": "$nota"},
            "nota_max": {"$max": "$nota"}
        }}
    ]
    
    stats = list(mongo.db.avaliacoes.aggregate(pipeline))
    
    if not stats:
        return jsonify({
            "aula": scrub(aula),
            "total_avaliacoes": 0,
            "nota_media": 0,
            "nota_min": 0,
            "nota_max": 0
        })
    
    result = stats[0]
    result.pop("_id", None)
    result["aula"] = scrub(aula)
    
    return jsonify(result)
