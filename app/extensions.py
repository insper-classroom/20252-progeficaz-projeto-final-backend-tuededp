from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timezone
from pymongo import MongoClient
import os

try:
    import mongomock
except Exception:
    mongomock = None

cors = CORS()
jwt = JWTManager()

class Mongo:
    client = None
    db = None
    def init_app(self, app):
        uri = app.config["MONGODB_URI"]
        name = app.config["MONGO_DB"]

        use_mock = (
            bool(app.config.get("USE_MOCK_DB"))
            or "PYTEST_CURRENT_TEST" in os.environ
        )

        if use_mock and mongomock is not None:
            self.client = mongomock.MongoClient()
            self.db = self.client[name]
            return

        try:
            self.client = MongoClient(uri, tz_aware=True, tzinfo=timezone.utc)
            self.client.admin.command("ping")
            self.db = self.client[name]
        except Exception:
            if mongomock is None:
                raise
            self.client = mongomock.MongoClient()
            self.db = self.client[name]

mongo = Mongo()
