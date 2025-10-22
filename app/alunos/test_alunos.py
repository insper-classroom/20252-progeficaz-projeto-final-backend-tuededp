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
def test_get_alunos(mock_mongo, client, auth_header):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = professores
    
    professores = [
        {"_id": ObjectId(), "nome": "João", "email": "joao@example.com"},
        {"_id": ObjectId(), "nome": "Maria", "email": "maria@example.com"},
    ]
    
    mock_mongo.db.professores.find.return_value = cursor
    mock_mongo.db.professores.count_documents.return_value = len(professores)

    response = client.get("/api/aluno/", headers=auth_header)
    assert response.status_code == 200, response.data
    body = response.get_json()
    assert body["total"] == 2
    assert isinstance(body["data"], list)
    assert body["data"][0]["nome"] == "João"
    assert body["data"][1]["nome"] == "Maria"

@patch('app.alunos.routes.mongo')
def test_get_id(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.professores.find_one.return_value = {
        "_id": oid, "nome": "João", "email": "joao@example.com"
    }

    response = client.get(f"/api/aluno/{oid}", headers=auth_header)
    assert response.status_code == 200
    data = response.get_json()
    # Retorna o _id corretamente
    assert data["_id"] == str(oid)
    assert data["nome"] == "João"
    assert data["email"] == "joao@example.com"

@patch('app.alunos.routes.mongo')
def test_get_aluno_id_invalido_400(mock_mongo, client, auth_header):
    response = client.get("/api/alunos/abc", headers=auth_header)
    assert response.status_code == 400

@patch('app.alunos.routes.mongo')
def test_get_aluno_nao_encontrado_404(mock_mongo, client, auth_header):
    mock_mongo.db.professores.find_one.return_value = None
    oid = ObjectId()
    response = client.get(f"/api/alunos/{oid}", headers=auth_header)
    assert response.status_code == 404

@patch('app.alunos.routes.mongo')
def test_novo_aluno(mock_mongo, client):
    oid = ObjectId()
    mock_mongo.db.professores.insert_one.return_value = MagicMock(inserted_id=oid)
    mock_mongo.db.professores.find_one.return_value = {"_id": oid, "nome": "Ana", "email": "ana@example.com"}

    professor = {"nome": "Ana", "email": "ana@example.com", "senha": "123"}
    response = client.post("/api/alunos/", json=professor)
    assert response.status_code == 201
    data = response.get_json()
    
    assert data["nome"] == "Ana"
    assert data["email"] == "ana@example.com"
    assert "_id" in data
    assert isinstance(data["_id"], str)
    assert "senha" not in data

@patch('app.alunos.routes.mongo')
def test_att_aluno(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.professores.update_one.return_value = MagicMock(matched_count=1)
    mock_mongo.db.professores.find_one.return_value = {
        "_id": oid, "nome": "Nome Atualizado", "email": "joao@example.com"
    }

    response = client.put(f"/api/alunos/{oid}", json={"nome": "Nome Atualizado"}, headers=auth_header)
    assert response.status_code == 200
    assert response.get_json()["nome"] == "Nome Atualizado"

@patch('app.alunos.routes.mongo')
def test_remove_aluno(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.professores.delete_one.return_value = MagicMock(deleted_count=1)

    response = client.delete(f"/api/professores/{oid}", headers=auth_header)
    assert response.status_code == 204