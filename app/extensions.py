from flask_cors import CORS
from datetime import timezone
from pymongo import MongoClient

cors = CORS()

class Mongo:
    client = None
    db = None
    def init_app(self, app):
        uri = app.config["MONGODB_URI"]
        name = app.config["MONGO_DB"]
        self.client = MongoClient(uri, tz_aware=True, tzinfo=timezone.utc)
        self.db = self.client[name]

mongo = Mongo()
