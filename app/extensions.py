from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timezone
from pymongo import MongoClient

cors = CORS()
jwt = JWTManager()

class Mongo:
    client = None
    db = None
    def init_app(self, app):
        uri = app.config["MONGODB_URI"]
        name = app.config["MONGO_DB"]
        self.client = MongoClient(uri, tz_aware=True, tzinfo=timezone.utc)
        self.db = self.client[name]

mongo = Mongo()
