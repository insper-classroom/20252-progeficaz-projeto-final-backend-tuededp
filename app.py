from app import create_app
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask import request, jsonify
from app.extensions import mongo
from app.utils import scrub
import os
import bcrypt

app = create_app()

# Configurar JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "sua-chave-secreta-super-segura")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # Tokens não expiram por padrão
jwt = JWTManager(app)

# Endpoint de teste
@app.route('/api/auth/test', methods=['GET'])
def test():
    """Endpoint de teste"""
    return jsonify({"msg": "Sistema funcionando"}), 200

# Endpoint para testar acesso ao banco
@app.route('/api/auth/test-db', methods=['GET'])
def test_db():
    """Endpoint para testar acesso ao banco"""
    try:
        from app.extensions import mongo
        
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

# Endpoint de login
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Endpoint para login de alunos e professores"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"msg": "Email e senha são obrigatórios"}), 400
        
        # Acessar o banco através do contexto da aplicação
        from app.extensions import mongo
        
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
                token = create_access_token(identity=token_data)
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
                token = create_access_token(identity=token_data)
                return jsonify({
                    "access_token": token,
                    "user": scrub(professor),
                    "tipo": "professor"
                }), 200
        
        # Se chegou aqui, credenciais inválidas
        return jsonify({"msg": "Email ou senha inválidos"}), 401
        
    except Exception as e:
        return jsonify({"msg": f"Erro no login: {str(e)}"}), 500

# Endpoint para verificar token
@app.route('/api/auth/verificar', methods=['GET'])
@jwt_required()
def verificar():
    """Endpoint para verificar se o token é válido"""
    try:
        user_data = get_jwt_identity()
        return jsonify({
            "msg": "Token válido",
            "user_id": user_data.get('user_id'),
            "email": user_data.get('email'),
            "nome": user_data.get('nome'),
            "tipo": user_data.get('tipo')
        }), 200
    except Exception as e:
        return jsonify({"msg": f"Erro na verificação: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
