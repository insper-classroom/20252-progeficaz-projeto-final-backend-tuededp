import pytest
from unittest.mock import patch, MagicMock
from bson.objectid import ObjectId
from app import create_app
from flask_jwt_extended import create_access_token

flask_app = create_app()

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client

@pytest.fixture
def auth_header():
    # Gera um token para as rotas com @jwt_required() 
    with flask_app.app_context():
        token = create_access_token(identity="tester")
    return {"Authorization": f"Bearer {token}"}

@patch('app.alunos.routes.mongo')
def test_create_success(mock_mongo, client):
    oid = ObjectId()
    
    mock_mongo.db.alunos.count_documents.return_value = 0
    mock_mongo.db.alunos.insert_one.return_value = MagicMock(inserted_id=oid)
    mock_mongo.db.alunos.find_one.return_value = {"_id": oid, "nome": "Ana", "email": "ana@example.com"}

    aluno = {"nome": "Ana", "email": "ana@example.com", "senha": "123"}
    response = client.post("/api/alunos/", json=aluno)
    assert response.status_code == 201
    data = response.get_json()
    
    assert data["nome"] == "Ana"
    assert data["email"] == "ana@example.com"
    assert "_id" in data
    assert isinstance(data["_id"], str)
    assert "senha" not in data

@patch('app.alunos.routes.mongo')
def test_list_success(mock_mongo, client, auth_header):
    alunos = [
        {"_id": ObjectId(), "nome": "Felipe", "email": "felipe@example.com"},
        {"_id": ObjectId(), "nome": "Alberto", "email": "albertin@example.com"},
    ]
    
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = alunos
    
    mock_mongo.db.alunos.find.return_value = cursor
    mock_mongo.db.alunos.count_documents.return_value = len(alunos)

    response = client.get("/api/alunos/", headers=auth_header)
    assert response.status_code == 200, response.data
    body = response.get_json()
    assert body["total"] == 2
    assert isinstance(body["data"], list)
    assert body["data"][0]["nome"] == "Felipe"
    assert body["data"][1]["nome"] == "Alberto"

@patch('app.alunos.routes.mongo')
def test_get_by_id_success(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.alunos.find_one.return_value = {"_id": oid, "nome": "Pedro", "email": "pedro@example.com"}

    response = client.get(f"/api/alunos/{oid}", headers=auth_header)
    assert response.status_code == 200
    data = response.get_json()
    # Retorna o _id corretamente
    assert data["_id"] == str(oid)
    assert data["nome"] == "Pedro"
    assert data["email"] == "pedro@example.com"

@patch('app.alunos.routes.mongo')
def test_get_aluno_id_invalido_400(mock_mongo, client, auth_header):
    response = client.get("/api/alunos/abc", headers=auth_header)
    assert response.status_code == 400

@patch('app.alunos.routes.mongo')
def test_get_aluno_nao_encontrado_404(mock_mongo, client, auth_header):
    mock_mongo.db.alunos.find_one.return_value = None
    oid = ObjectId()
    response = client.get(f"/api/alunos/{oid}", headers=auth_header)
    assert response.status_code == 404

@patch('app.alunos.routes.mongo')
def test_update_success(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.alunos.update_one.return_value = MagicMock(matched_count=1)
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": oid, "nome": "Nome Atualizado", "email": "joao@example.com"
    }

    response = client.put(f"/api/alunos/{oid}", json={"nome": "Nome Atualizado"}, headers=auth_header)
    assert response.status_code == 200
    assert response.get_json()["nome"] == "Nome Atualizado"

@patch('app.alunos.routes.mongo')
def test_delete_success(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.alunos.delete_one.return_value = MagicMock(deleted_count=1)

    response = client.delete(f"/api/alunos/{oid}", headers=auth_header)
    assert response.status_code == 204