import os
from flask import Flask
from .extensions import cors, mongo, jwt
from .alunos.routes import bp as alunos_bp
from .professores.routes import bp as profs_bp
from .auth.routes import bp as auth_bp
from .aulas.routes import bp as aulas_bp
from .categorias.routes import bp as categorias_bp
from .agenda.routes import bp as agenda_bp
from .chats.routes import bp as chats_bp
from .avaliacoes.routes import bp as avaliacoes_bp
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    # Config básica via env
    app.config["MONGODB_URI"] = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    app.config["MONGO_DB"]    = os.getenv("MONGO_DB", "app_dev")
    app.config["CORS_ORIGINS"]= os.getenv("CORS_ORIGINS", "*").split(",")
    app.config["JSON_SORT_KEYS"] = False
    app.config["SHOW_HASH"] = os.getenv("SHOW_HASH", "false").lower() == "true"
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]  # usa header
    # Habilita mock de DB automaticamente em testes ou via env
    app.config["USE_MOCK_DB"] = (
        os.getenv("USE_MOCK_DB", "").lower() in {"1", "true", "yes"}
        or "PYTEST_CURRENT_TEST" in os.environ
    )
    
    # JWT Configuration
    app.config["JWT_HEADER_NAME"]   = "Authorization"
    app.config["JWT_HEADER_TYPE"]   = "Bearer"
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "sua-chave-secreta-super-segura")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # Tokens não expiram por padrão

    cors.init_app(
    app,
    resources={
        r"/api/*": {
            "origins": app.config["CORS_ORIGINS"],
            "allow_headers": ["Content-Type", "Authorization"],   # <- libera Authorization
            "expose_headers": ["Authorization"],
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        }
    },
    supports_credentials=False,  # true só se você for usar cookies
)
    mongo.init_app(app)
    jwt.init_app(app)

    # Índices essenciais (idempotentes)
    mongo.db.alunos.create_index("email", unique=True)
    mongo.db.professores.create_index("email", unique=True)
    mongo.db.alunos.create_index([("created_at", -1)])
    mongo.db.professores.create_index([("created_at", -1)])
    
    # Índices para aulas
    mongo.db.aulas.create_index("id_professor")
    mongo.db.aulas.create_index("id_categoria")
    mongo.db.aulas.create_index("status")
    mongo.db.aulas.create_index([("created_at", -1)])
    mongo.db.aulas.create_index([("titulo", "text"), ("descricao_aula", "text")])
    
    # Índices para categorias
    mongo.db.categorias.create_index("nome", unique=True)
    mongo.db.categorias.create_index([("created_at", -1)])
    
    # Índices para agenda
    mongo.db.agenda.create_index("id_aluno")
    mongo.db.agenda.create_index("id_professor")
    mongo.db.agenda.create_index("id_aula")
    mongo.db.agenda.create_index("status")
    mongo.db.agenda.create_index("data_hora")
    mongo.db.agenda.create_index([("id_professor", 1), ("data_hora", 1)])
    mongo.db.agenda.create_index([("id_aluno", 1), ("data_hora", 1)])
    mongo.db.agenda.create_index([("created_at", -1)])
    
    # Índices para avaliações
    mongo.db.avaliacoes.create_index("id_aluno")
    mongo.db.avaliacoes.create_index("id_prof")
    mongo.db.avaliacoes.create_index("id_aula")
    mongo.db.avaliacoes.create_index([("id_aluno", 1), ("id_aula", 1)], unique=True)
    mongo.db.avaliacoes.create_index([("created_at", -1)])
    
    # Índices para status de aulas
    mongo.db.status_aulas.create_index("id_aula")
    mongo.db.status_aulas.create_index("id_professor")
    mongo.db.status_aulas.create_index("data_hora")
    mongo.db.status_aulas.create_index([("created_at", -1)])

    # Rotas
    app.register_blueprint(auth_bp,        url_prefix="/api/auth")
    app.register_blueprint(alunos_bp,       url_prefix="/api/alunos")
    app.register_blueprint(profs_bp,        url_prefix="/api/professores")
    app.register_blueprint(aulas_bp,       url_prefix="/api/aulas")
    app.register_blueprint(categorias_bp,  url_prefix="/api/categorias")
    app.register_blueprint(agenda_bp,      url_prefix="/api/agenda")
    app.register_blueprint(avaliacoes_bp,  url_prefix="/api/avaliacoes")
    app.register_blueprint(chats_bp, url_prefix="/api/chats")

    return app
