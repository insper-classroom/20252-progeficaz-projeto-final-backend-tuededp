from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
from datetime import datetime
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "*").split(",")}})

URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGO_DB", "app_dev")

client = MongoClient(URI)
db = client[DB_NAME]

db.users.create_index("email", unique=True)

@app.route('/')
def index():
    """Página inicial da API"""
    return jsonify({
        'message': 'API Flask funcionando!',
        'status': 'success',
        'version': '1.0.0'
    })

if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=3000
    )