# app/auth/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from app.extensions import mongo
from app.utils import scrub
import bcrypt
import requests

bp = Blueprint("auth", __name__)

@bp.route("/test", methods=["GET"])
def test():
    return jsonify({"msg": "Sistema funcionando"}), 200

@bp.route("/test-db", methods=["GET"])
def test_db():
    try:
        alunos_count = mongo.db.alunos.count_documents({})
        aluno_exemplo = mongo.db.alunos.find_one({})
        return jsonify({
            "msg": "Conexão com banco OK",
            "alunos_count": alunos_count,
            "aluno_exemplo": scrub(aluno_exemplo) if aluno_exemplo else None
        }), 200
    except Exception as e:
        return jsonify({"msg": f"Erro no banco: {str(e)}"}), 500

# ---- PRE-FLIGHT (CORS) ----
@bp.route("/login", methods=["OPTIONS"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def login_preflight():
    return ("", 204)

# ---- LOGIN (POST /api/auth/login e /api/auth/login/) ----
@bp.route("/login", methods=["POST"], strict_slashes=False)
@cross_origin(headers=["Content-Type", "Authorization"])
def login():
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "")

        if not email or not password:
            return jsonify({"msg": "Email e senha são obrigatórios"}), 400

        # Tenta aluno
        aluno = mongo.db.alunos.find_one({"email": email})
        if aluno and bcrypt.checkpw(password.encode("utf-8"), aluno["senha_hash"].encode("utf-8")):
            token = create_access_token(
                identity=str(aluno["_id"]),
                additional_claims={"email": aluno["email"], "nome": aluno["nome"], "tipo": "aluno"},
            )
            return jsonify({"access_token": token, "user": scrub(aluno), "tipo": "aluno"}), 200

        # Tenta professor
        professor = mongo.db.professores.find_one({"email": email})
        if professor and bcrypt.checkpw(password.encode("utf-8"), professor["senha_hash"].encode("utf-8")):
            token = create_access_token(
                identity=str(professor["_id"]),
                additional_claims={"email": professor["email"], "nome": professor["nome"], "tipo": "professor"},
            )
            return jsonify({"access_token": token, "user": scrub(professor), "tipo": "professor"}), 200

        return jsonify({"msg": "Email ou senha inválidos"}), 401
    except Exception as e:
        return jsonify({"msg": f"Erro no login: {str(e)}"}), 500

# ---- VERIFICAR TOKEN ----
@bp.route("/verificar", methods=["GET"])
@cross_origin(headers=["Content-Type", "Authorization"])
@jwt_required()
def verificar():
    try:
        user_id = get_jwt_identity()
        claims = get_jwt()
        return jsonify({
            "msg": "Token válido",
            "user_id": user_id,
            "email": claims.get("email"),
            "nome": claims.get("nome"),
            "tipo": claims.get("tipo"),
        }), 200
    except Exception as e:
        return jsonify({"msg": f"Erro na verificação: {str(e)}"}), 500

# ---- CEP (extra) ----
@bp.route("/checa_cep/<cep>", methods=["GET"])
def checa_cep(cep):
    digitos_cep = "".join(num for num in cep if num.isdigit())
    if len(digitos_cep) != 8:
        return jsonify({"error": "CEP inválido", "msg": "CEP deve conter 8 dígitos"}), 400

    try:
        resp = requests.get(f"https://viacep.com.br/ws/{digitos_cep}/json/", timeout=5)
    except requests.RequestException:
        current_app.logger.exception("Erro ao consultar ViaCEP")
        return jsonify({"error": "failed_lookup", "msg": "Erro ao consultar serviço de CEP"}), 502

    if resp.status_code != 200:
        return jsonify({"error": "via_cep_error", "msg": "ViaCEP retornou erro"}), 502

    data = resp.json()
    if data.get("erro"):
        return jsonify({"error": "not_found", "msg": "CEP não encontrado"}), 404

    return jsonify(data), 200
