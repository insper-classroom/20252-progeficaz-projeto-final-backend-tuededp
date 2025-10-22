from flask import Blueprint, request, jsonify
from pymongo.errors import DuplicateKeyError
from ..extensions import mongo
from ..utils import oid, now, scrub

bp = Blueprint("avaliacoes", __name__)

AVALIACAO_FIELDS = {"id_aluno", "id_prof", "id_aula", "nota", "comentario"}

@bp.post("/")
def create():
    """Criar nova avaliação"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"msg": "Dados são obrigatórios"}), 400
        
        # Validar campos obrigatórios
        missing_fields = AVALIACAO_FIELDS - set(data.keys())
        if missing_fields:
            return jsonify({"msg": f"Campos obrigatórios: {', '.join(missing_fields)}"}), 400
        
        # Criar avaliação
        avaliacao = {
            "_id": oid(),
            "id_aluno": data["id_aluno"],
            "id_prof": data["id_prof"],
            "id_aula": data["id_aula"],
            "nota": data["nota"],
            "comentario": data.get("comentario", ""),
            "created_at": now(),
            "updated_at": now()
        }
        
        mongo.db.avaliacoes.insert_one(avaliacao)
        return jsonify(scrub(avaliacao)), 201
        
    except DuplicateKeyError:
        return jsonify({"msg": "Avaliação já existe para esta aula"}), 409
    except Exception as e:
        return jsonify({"msg": f"Erro ao criar avaliação: {str(e)}"}), 500

@bp.get("/")
def list_():
    """Listar todas as avaliações"""
    try:
        avaliacoes = list(mongo.db.avaliacoes.find({}))
        return jsonify([scrub(av) for av in avaliacoes]), 200
    except Exception as e:
        return jsonify({"msg": f"Erro ao listar avaliações: {str(e)}"}), 500

@bp.get("/<id>")
def get_(id):
    """Buscar avaliação por ID"""
    try:
        avaliacao = mongo.db.avaliacoes.find_one({"_id": oid(id)})
        if not avaliacao:
            return jsonify({"msg": "Avaliação não encontrada"}), 404
        return jsonify(scrub(avaliacao)), 200
    except Exception as e:
        return jsonify({"msg": f"Erro ao buscar avaliação: {str(e)}"}), 500

@bp.put("/<id>")
def update(id):
    """Atualizar avaliação"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"msg": "Dados são obrigatórios"}), 400
        
        # Atualizar apenas campos permitidos
        update_data = {k: v for k, v in data.items() if k in AVALIACAO_FIELDS}
        if not update_data:
            return jsonify({"msg": "Nenhum campo válido para atualizar"}), 400
        
        update_data["updated_at"] = now()
        
        result = mongo.db.avaliacoes.update_one(
            {"_id": oid(id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"msg": "Avaliação não encontrada"}), 404
        
        return jsonify({"msg": "Avaliação atualizada com sucesso"}), 200
        
    except Exception as e:
        return jsonify({"msg": f"Erro ao atualizar avaliação: {str(e)}"}), 500

@bp.delete("/<id>")
def delete(id):
    """Deletar avaliação"""
    try:
        result = mongo.db.avaliacoes.delete_one({"_id": oid(id)})
        if result.deleted_count == 0:
            return jsonify({"msg": "Avaliação não encontrada"}), 404
        return jsonify({"msg": "Avaliação deletada com sucesso"}), 200
    except Exception as e:
        return jsonify({"msg": f"Erro ao deletar avaliação: {str(e)}"}), 500
