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

@patch('app.professores.routes.mongo')
def test_create_success(mock_mongo, client):
    oid = ObjectId()
    
    # ensure_unique_slug usa count_documents - retorna 0 (slug livre)
    mock_mongo.db.professores.count_documents.return_value = 0
    # find_one é chamado apenas no final para buscar o doc inserido
    mock_mongo.db.professores.find_one.return_value = {"_id": oid, "nome": "Ana", "email": "ana@example.com"}
    mock_mongo.db.professores.insert_one.return_value = MagicMock(inserted_id=oid)

    professor = {"nome": "Ana", "email": "ana@example.com", "senha": "123"}
    response = client.post("/api/professores/", json=professor)
    assert response.status_code == 201
    data = response.get_json()
    
    assert data["nome"] == "Ana"
    assert data["email"] == "ana@example.com"
    assert "_id" in data
    assert isinstance(data["_id"], str)
    assert "senha" not in data

@patch('app.professores.routes.mongo')
def test_list_success(mock_mongo, client, auth_header):
    professores = [
        {"_id": ObjectId(), "nome": "João", "email": "joao@example.com"},
        {"_id": ObjectId(), "nome": "Maria", "email": "maria@example.com"},
    ]
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = professores
    
    
    mock_mongo.db.professores.find.return_value = cursor
    mock_mongo.db.professores.count_documents.return_value = len(professores)

    response = client.get("/api/professores/", headers=auth_header)
    assert response.status_code == 200, response.data
    body = response.get_json()
    assert body["total"] == 2
    assert isinstance(body["data"], list)
    assert body["data"][0]["nome"] == "João"
    assert body["data"][1]["nome"] == "Maria"

@patch('app.professores.routes.mongo')
def test_get_by_id_success(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.professores.find_one.return_value = {
        "_id": oid, "nome": "João", "email": "joao@example.com"
    }

    response = client.get(f"/api/professores/{oid}", headers=auth_header)
    assert response.status_code == 200
    data = response.get_json()
    # Retorna o _id corretamente
    assert data["_id"] == str(oid)
    assert data["nome"] == "João"
    assert data["email"] == "joao@example.com"

@patch('app.professores.routes.mongo')
def test_get_professor_id_invalido_400(mock_mongo, client, auth_header):
    response = client.get("/api/professores/abc", headers=auth_header)
    assert response.status_code == 400

@patch('app.professores.routes.mongo')
def test_get_professor_nao_encontrado_404(mock_mongo, client, auth_header):
    mock_mongo.db.professores.find_one.return_value = None
    oid = ObjectId()
    response = client.get(f"/api/professores/{oid}", headers=auth_header)
    assert response.status_code == 404

@patch('app.professores.routes.mongo')
def test_update_success(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.professores.update_one.return_value = MagicMock(matched_count=1)
    
    # ensure_unique_slug usa count_documents - retorna 0 (slug livre)
    mock_mongo.db.professores.count_documents.return_value = 0
    
    # find_one chamadas na ordem:
    # 1) doc_atual (para decidir slug): retorna nome atual sem slug
    # 2) exists (slug em uso por outro?): None -> livre
    # 3) fetch final do documento atualizado
    mock_mongo.db.professores.find_one.side_effect = [
        {"_id": oid, "nome": "Nome Atualizado", "slug": None},  # doc_atual
        None,  # exists check
        {"_id": oid, "nome": "Nome Atualizado", "email": "joao@example.com"},  # fetch final
    ]

    response = client.put(f"/api/professores/{oid}", json={"nome": "Nome Atualizado"}, headers=auth_header)
    assert response.status_code == 200
    assert response.get_json()["nome"] == "Nome Atualizado"

@patch('app.professores.routes.mongo')
def test_delete_success(mock_mongo, client, auth_header):
    oid = ObjectId()
    mock_mongo.db.professores.delete_one.return_value = MagicMock(deleted_count=1)

    response = client.delete(f"/api/professores/{oid}", headers=auth_header)
    assert response.status_code == 204