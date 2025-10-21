from flask import Blueprint, request, jsonify
from pymongo.errors import DuplicateKeyError
from ..extensions import mongo
from ..utils import oid, now, scrub
from datetime import datetime, timezone

bp = Blueprint("agenda", __name__)

AGENDA_FIELDS = {"id_aluno", "id_professor", "id_aula", "data_hora", "status", "observacoes"}

@bp.post("/")
def create():
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in AGENDA_FIELDS}
    
    required_fields = ["id_aluno", "id_professor", "id_aula", "data_hora"]
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
    prof_id = oid(body.get("id_professor"))
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
    
    # Validar formato da data
    try:
        if isinstance(body["data_hora"], str):
            data_hora = datetime.fromisoformat(body["data_hora"].replace('Z', '+00:00'))
        else:
            data_hora = body["data_hora"]
        
        if data_hora.tzinfo is None:
            data_hora = data_hora.replace(tzinfo=timezone.utc)
        
        body["data_hora"] = data_hora
    except (ValueError, TypeError):
        return jsonify({"error": "invalid_datetime_format"}), 400
    
    # Verificar conflitos de horário para o professor
    conflito = mongo.db.agenda.find_one({
        "id_professor": prof_id,
        "data_hora": body["data_hora"],
        "status": {"$in": ["agendada", "confirmada"]}
    })
    if conflito:
        return jsonify({"error": "professor_schedule_conflict"}), 409
    
    # Verificar conflitos de horário para o aluno
    conflito_aluno = mongo.db.agenda.find_one({
        "id_aluno": aluno_id,
        "data_hora": body["data_hora"],
        "status": {"$in": ["agendada", "confirmada"]}
    })
    if conflito_aluno:
        return jsonify({"error": "aluno_schedule_conflict"}), 409
    
    body["status"] = body.get("status", "agendada")
    body["created_at"] = body["updated_at"] = now()
    
    try:
        res = mongo.db.agenda.insert_one(body)
    except Exception as e:
        return jsonify({"error": "creation_failed", "details": str(e)}), 500
    
    doc = mongo.db.agenda.find_one({"_id": res.inserted_id}, {})
    return jsonify(scrub(doc)), 201

@bp.get("/")
def list_():
    aluno = request.args.get("aluno")
    professor = request.args.get("professor")
    aula = request.args.get("aula")
    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    order = int(request.args.get("order", -1))
    sort = request.args.get("sort", "data_hora")
    
    filt = {}
    
    if aluno:
        aluno_id = oid(aluno)
        if aluno_id:
            filt["id_aluno"] = aluno_id
    
    if professor:
        prof_id = oid(professor)
        if prof_id:
            filt["id_professor"] = prof_id
    
    if aula:
        aula_id = oid(aula)
        if aula_id:
            filt["id_aula"] = aula_id
    
    if status:
        filt["status"] = status
    
    if data_inicio or data_fim:
        data_filtro = {}
        if data_inicio:
            try:
                data_inicio_dt = datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
                if data_inicio_dt.tzinfo is None:
                    data_inicio_dt = data_inicio_dt.replace(tzinfo=timezone.utc)
                data_filtro["$gte"] = data_inicio_dt
            except (ValueError, TypeError):
                return jsonify({"error": "invalid_data_inicio_format"}), 400
        
        if data_fim:
            try:
                data_fim_dt = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
                if data_fim_dt.tzinfo is None:
                    data_fim_dt = data_fim_dt.replace(tzinfo=timezone.utc)
                data_filtro["$lte"] = data_fim_dt
            except (ValueError, TypeError):
                return jsonify({"error": "invalid_data_fim_format"}), 400
        
        filt["data_hora"] = data_filtro
    
    cur = (mongo.db.agenda.find(filt, {})
           .sort(sort, order)
           .skip((page-1)*limit)
           .limit(limit))
    total = mongo.db.agenda.count_documents(filt)
    
    # Enriquecer dados
    agendamentos = []
    for agendamento in cur:
        agendamento_doc = scrub(agendamento)
        
        # Buscar dados do aluno
        if agendamento.get("id_aluno"):
            aluno = mongo.db.alunos.find_one({"_id": agendamento["id_aluno"]}, {"nome": 1, "email": 1, "telefone": 1})
            if aluno:
                agendamento_doc["aluno"] = {
                    "id": str(aluno["_id"]),
                    "nome": aluno.get("nome"),
                    "email": aluno.get("email"),
                    "telefone": aluno.get("telefone")
                }
        
        # Buscar dados do professor
        if agendamento.get("id_professor"):
            prof = mongo.db.professores.find_one({"_id": agendamento["id_professor"]}, {"nome": 1, "email": 1, "telefone": 1})
            if prof:
                agendamento_doc["professor"] = {
                    "id": str(prof["_id"]),
                    "nome": prof.get("nome"),
                    "email": prof.get("email"),
                    "telefone": prof.get("telefone")
                }
        
        # Buscar dados da aula
        if agendamento.get("id_aula"):
            aula = mongo.db.aulas.find_one({"_id": agendamento["id_aula"]}, {"titulo": 1, "descricao_aula": 1, "preco_decimal": 1})
            if aula:
                agendamento_doc["aula"] = {
                    "id": str(aula["_id"]),
                    "titulo": aula.get("titulo"),
                    "descricao_aula": aula.get("descricao_aula"),
                    "preco_decimal": aula.get("preco_decimal")
                }
        
        agendamentos.append(agendamento_doc)
    
    return jsonify({"data": agendamentos, "total": total, "page": page, "limit": limit})

@bp.get("/<id>")
def get_(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    doc = mongo.db.agenda.find_one({"_id": _id}, {})
    if not doc:
        return jsonify({"error": "not_found"}), 404
    
    agendamento_doc = scrub(doc)
    
    # Enriquecer com dados completos
    if doc.get("id_aluno"):
        aluno = mongo.db.alunos.find_one({"_id": doc["id_aluno"]})
        if aluno:
            agendamento_doc["aluno"] = scrub(aluno)
    
    if doc.get("id_professor"):
        prof = mongo.db.professores.find_one({"_id": doc["id_professor"]})
        if prof:
            agendamento_doc["professor"] = scrub(prof)
    
    if doc.get("id_aula"):
        aula = mongo.db.aulas.find_one({"_id": doc["id_aula"]})
        if aula:
            agendamento_doc["aula"] = scrub(aula)
    
    return jsonify(agendamento_doc)

@bp.put("/<id>")
def update(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    data = request.get_json(force=True) or {}
    body = {k: v for k, v in data.items() if k in AGENDA_FIELDS}
    
    # Validar referências se fornecidas
    if body.get("id_aluno"):
        aluno_id = oid(body.get("id_aluno"))
        if not aluno_id:
            return jsonify({"error": "invalid_aluno_id"}), 400
        
        aluno = mongo.db.alunos.find_one({"_id": aluno_id})
        if not aluno:
            return jsonify({"error": "aluno_not_found"}), 404
    
    if body.get("id_professor"):
        prof_id = oid(body.get("id_professor"))
        if not prof_id:
            return jsonify({"error": "invalid_professor_id"}), 400
        
        professor = mongo.db.professores.find_one({"_id": prof_id})
        if not professor:
            return jsonify({"error": "professor_not_found"}), 404
    
    if body.get("id_aula"):
        aula_id = oid(body.get("id_aula"))
        if not aula_id:
            return jsonify({"error": "invalid_aula_id"}), 400
        
        aula = mongo.db.aulas.find_one({"_id": aula_id})
        if not aula:
            return jsonify({"error": "aula_not_found"}), 404
    
    # Validar formato da data se fornecida
    if body.get("data_hora"):
        try:
            if isinstance(body["data_hora"], str):
                data_hora = datetime.fromisoformat(body["data_hora"].replace('Z', '+00:00'))
            else:
                data_hora = body["data_hora"]
            
            if data_hora.tzinfo is None:
                data_hora = data_hora.replace(tzinfo=timezone.utc)
            
            body["data_hora"] = data_hora
        except (ValueError, TypeError):
            return jsonify({"error": "invalid_datetime_format"}), 400
    
    if not body:
        return jsonify({"error": "no_fields_to_update"}), 400
    
    body["updated_at"] = now()
    
    r = mongo.db.agenda.update_one({"_id": _id}, {"$set": body})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404
    
    doc = mongo.db.agenda.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))

@bp.delete("/<id>")
def delete(id):
    _id = oid(id)
    if not _id:
        return jsonify({"error": "invalid_id"}), 400
    
    r = mongo.db.agenda.delete_one({"_id": _id})
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
    status_validos = ["agendada", "confirmada", "cancelada", "concluida", "ausente"]
    if novo_status not in status_validos:
        return jsonify({"error": "invalid_status", "valid_statuses": status_validos}), 400
    
    r = mongo.db.agenda.update_one({"_id": _id}, {"$set": {"status": novo_status, "updated_at": now()}})
    if r.matched_count == 0:
        return jsonify({"error": "not_found"}), 404
    
    doc = mongo.db.agenda.find_one({"_id": _id}, {})
    return jsonify(scrub(doc))