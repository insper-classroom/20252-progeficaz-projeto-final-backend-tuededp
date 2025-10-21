import os
from flask import Flask
from .extensions import cors, mongo
from .alunos.routes import bp as alunos_bp
from .professores.routes import bp as profs_bp
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

    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    mongo.init_app(app)

    # Índices essenciais (idempotentes)
    mongo.db.alunos.create_index("email", unique=True)
    mongo.db.professores.create_index("email", unique=True)
    mongo.db.alunos.create_index([("created_at", -1)])
    mongo.db.professores.create_index([("created_at", -1)])

    # Rotas
    app.register_blueprint(alunos_bp,      url_prefix="/api/alunos")
    app.register_blueprint(profs_bp,       url_prefix="/api/professores")

    return app
