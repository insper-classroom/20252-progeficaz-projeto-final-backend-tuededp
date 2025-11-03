import pytest
from unittest.mock import patch, MagicMock
from bson import ObjectId
from datetime import datetime, timezone
from flask_jwt_extended import create_access_token
from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _auth_headers(app, identity='507f1f77bcf86cd799439011', claims=None):
    if claims is None:
        claims = {"email": "user@example.com", "nome": "User", "tipo": "aluno"}
    with app.app_context():
        token = create_access_token(identity=identity, additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    resp = client.get('/api/chats/health')
    assert resp.status_code == 200
    assert resp.get_json().get('ok') is True


@patch('app.chats.routes.mongo')
def test_list_conversas_success(mock_mongo, app, client):
    me_id = ObjectId()
    # conversa simulada sem last_message; rota deve completar consultando messages
    conv = {
        "_id": ObjectId(),
        "members": [me_id, ObjectId()],
        "last_message": None,
        "created_at": datetime(2025, 11, 3, 10, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 11, 3, 12, 0, tzinfo=timezone.utc),
    }
    # cursor encadeável
    mock_cur = MagicMock()
    mock_cur.sort.return_value = [conv]
    mock_mongo.db.conversations.find.return_value = mock_cur

    # last message para completar payload
    last_msg = {
        "_id": ObjectId(),
        "conversation_id": conv["_id"],
        "text": "olá",
        "from": me_id,
        "created_at": datetime(2025, 11, 3, 11, 0, tzinfo=timezone.utc)
    }
    mock_mongo.db.messages.find_one.return_value = last_msg

    # dados do outro usuário
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": conv["members"][1],
        "nome": "Aluno 2",
        "email": "a2@example.com",
        "avatar_url": "http://x/y.png",
        "headline": "Estudante",
    }

    headers = _auth_headers(app, identity=str(me_id))
    resp = client.get('/api/chats/', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list) and len(data) == 1
    c0 = data[0]
    assert c0["id"] == str(conv["_id"])
    assert c0["other"]["nome"] == "Aluno 2"
    assert c0["last_message"]["text"] == "olá"


@patch('app.chats.routes.mongo')
def test_create_or_get_existing_conversation(mock_mongo, app, client):
    me_id = ObjectId()
    other_id = ObjectId()
    existing = {
        "_id": ObjectId(),
        "members": [me_id, other_id],
        "last_message": {"text": "oi", "at": "2025-11-03T10:00:00Z", "from": str(me_id)},
        "created_at": datetime(2025, 11, 3, 9, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 11, 3, 10, 0, tzinfo=timezone.utc),
    }
    # primeira busca encontra; a segunda nem será chamada
    mock_mongo.db.conversations.find_one.side_effect = [existing]
    # Retornar usuário 'other' como dict real para evitar MagicMock no jsonify
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": other_id,
        "nome": "Aluno X",
        "email": "x@example.com",
        "avatar_url": None,
        "headline": "Aluno",
    }

    headers = _auth_headers(app, identity=str(me_id))
    resp = client.post('/api/chats/', json={"user_id": str(other_id)}, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == str(existing["_id"])  # reutilizou conversa


@patch('app.chats.routes.mongo')
def test_create_chat(mock_mongo, app, client):
    me_id = ObjectId()
    other_id = ObjectId()

    # não existe conversa; cria nova
    mock_mongo.db.conversations.find_one.side_effect = [None, None]
    ins_id = ObjectId()
    mock_mongo.db.conversations.insert_one.return_value = MagicMock(inserted_id=ins_id)
    # Não há última mensagem para completar automaticamente
    mock_mongo.db.messages.find_one.return_value = None

    # enriquecer "other" na resposta
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": other_id,
        "nome": "Aluno B",
        "email": "b@example.com",
        "avatar_url": None,
        "headline": None,
    }

    headers = _auth_headers(app, identity=str(me_id))
    resp = client.post('/api/chats/', json={"user_id": str(other_id)}, headers=headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["members"][0] == str(me_id)
    assert data["other"]["id"] == str(other_id)


@patch('app.chats.routes.mongo')
def test_list_mensagens_success(mock_mongo, app, client):
    me_id = ObjectId()
    conv_id = ObjectId()

    # conversa existe e contem o usuário
    mock_mongo.db.conversations.find_one.return_value = {
        "_id": conv_id,
        "members": [me_id, ObjectId()],
    }

    # mensagens ordenadas
    m1 = {
        "_id": ObjectId(),
        "conversation_id": conv_id,
        "from": me_id,
        "text": "Oi",
        "created_at": datetime(2025, 11, 3, 10, 0, tzinfo=timezone.utc)
    }
    m2 = {
        "_id": ObjectId(),
        "conversation_id": conv_id,
        "from": ObjectId(),
        "text": "Tudo bem",
        "created_at": datetime(2025, 11, 3, 10, 5, tzinfo=timezone.utc)
    }

    mock_msgs_cur = MagicMock()
    mock_msgs_cur.sort.return_value = mock_msgs_cur
    mock_msgs_cur.limit.return_value = [m1, m2]
    mock_mongo.db.messages.find.return_value = mock_msgs_cur

    headers = _auth_headers(app, identity=str(me_id))
    resp = client.get(f'/api/chats/{str(conv_id)}/messages', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]['fromMe'] is True
    assert data[1]['fromMe'] is False


@patch('app.chats.routes.mongo')
def test_enviar_mensagem_success(mock_mongo, app, client):
    me_id = ObjectId()
    conv_id = ObjectId()

    mock_mongo.db.conversations.find_one.return_value = {
        "_id": conv_id,
        "members": [me_id, ObjectId()],
    }

    ins_msg_id = ObjectId()
    mock_mongo.db.messages.insert_one.return_value = MagicMock(inserted_id=ins_msg_id)

    headers = _auth_headers(app, identity=str(me_id))
    resp = client.post(
        f'/api/chats/{str(conv_id)}/messages',
        headers=headers,
        json={"text": "Olá!"}
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['id'] == str(ins_msg_id)
    assert data['fromMe'] is True
