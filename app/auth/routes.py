from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.extensions import mongo
from app.utils import scrub
import bcrypt
import requests
from flask import current_app

bp = Blueprint('auth', __name__)

@bp.route('/test', methods=['GET'])
def test():
    """Endpoint de teste"""
    return jsonify({"msg": "Sistema funcionando"}), 200

@bp.route('/test-db', methods=['GET'])
def test_db():
    """Endpoint para testar acesso ao banco"""
    try:
        # Contar alunos
        alunos_count = mongo.db.alunos.count_documents({})
        
        # Buscar um aluno de exemplo
        aluno_exemplo = mongo.db.alunos.find_one({})
        
        return jsonify({
            "msg": "Conexão com banco OK",
            "alunos_count": alunos_count,
            "aluno_exemplo": scrub(aluno_exemplo) if aluno_exemplo else None
        }), 200
        
    except Exception as e:
        return jsonify({"msg": f"Erro no banco: {str(e)}"}), 500

@bp.route('/login', methods=['POST'])
def login():
    """Endpoint para login de alunos e professores"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"msg": "Email e senha são obrigatórios"}), 400
        
        # Buscar em alunos primeiro
        aluno = mongo.db.alunos.find_one({"email": email.strip().lower()})
        if aluno:
            # Verificar senha do aluno
            if bcrypt.checkpw(password.encode('utf-8'), aluno['senha_hash'].encode('utf-8')):
                # Criar token JWT com informações do aluno
                token_data = {
                    "user_id": str(aluno['_id']),
                    "email": aluno['email'],
                    "nome": aluno['nome'],
                    "tipo": "aluno"
                }
                token = create_access_token(identity=str(aluno['_id']), additional_claims=token_data)
                return jsonify({
                    "access_token": token,
                    "user": scrub(aluno),
                    "tipo": "aluno"
                }), 200
        
        # Buscar em professores se não encontrou em alunos
        professor = mongo.db.professores.find_one({"email": email.strip().lower()})
        if professor:
            # Verificar senha do professor
            if bcrypt.checkpw(password.encode('utf-8'), professor['senha_hash'].encode('utf-8')):
                # Criar token JWT com informações do professor
                token_data = {
                    "user_id": str(professor['_id']),
                    "email": professor['email'],
                    "nome": professor['nome'],
                    "tipo": "professor"
                }
                token = create_access_token(identity=str(professor['_id']), additional_claims=token_data)
                return jsonify({
                    "access_token": token,
                    "user": scrub(professor),
                    "tipo": "professor"
                }), 200
        
        # Se chegou aqui, credenciais inválidas
        return jsonify({"msg": "Email ou senha inválidos"}), 401
        
    except Exception as e:
        return jsonify({"msg": f"Erro no login: {str(e)}"}), 500

@bp.route('/verificar', methods=['GET'])
@jwt_required()
def verificar():
    """Endpoint para verificar se o token é válido"""
    try:
        from flask_jwt_extended import get_jwt
        user_id = get_jwt_identity()
        claims = get_jwt()
        
        return jsonify({
            "msg": "Token válido",
            "user_id": user_id,
            "email": claims.get('email'),
            "nome": claims.get('nome'),
            "tipo": claims.get('tipo')
        }), 200
    except Exception as e:
        return jsonify({"msg": f"Erro na verificação: {str(e)}"}), 500

@bp.route('/checa_cep/<cep>', methods=['GET'])
def checa_cep(cep):
    """ 
    Essa função serve para checar se o CEP é valido, retornando os erros caso nao seja
    """
        
    digitos_cep = ''.join(num for num in cep if num.isdigit())
    if len(digitos_cep) != 8:
        return jsonify({"error": "CEP inválido", "msg": "CEP deve conter 8 dígitos"}), 400

    try:
        resp = requests.get(f'https://viacep.com.br/ws/{digitos_cep}/json/', timeout=5)
    except requests.RequestException as e:
        current_app.logger.exception("Erro ao consultar ViaCEP")
        return jsonify({"error": "failed_lookup", "msg": "Erro ao consultar serviço de CEP"}), 502

    if resp.status_code != 200:
        return jsonify({"error": "via_cep_error", "msg": "ViaCEP retornou erro"}), 502

    data = resp.json()
    if data.get("erro"):
        return jsonify({"error": "not_found", "msg": "CEP não encontrado"}), 404

    return jsonify(data), 200