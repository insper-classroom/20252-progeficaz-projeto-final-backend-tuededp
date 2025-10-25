import pytest
from unittest.mock import patch, MagicMock
from bson import ObjectId
from datetime import datetime, timezone
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@patch('app.aulas.routes.mongo')
def test_create_success(mock_mongo, client):
    # IDs fictícios
    prof_id = ObjectId()
    cat_id = ObjectId()
    
    # Mock professor 
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id, 
        "nome": "Prof. João"
    }
    
    # Mock categoria
    mock_mongo.db.categorias.find_one.return_value = {
        "_id": cat_id, 
        "nome": "Matemática"
    }
    
    # simula a inserção no mongo
    inserted_id = ObjectId()
    mock_mongo.db.aulas.insert_one.return_value = MagicMock(inserted_id=inserted_id)
   
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": inserted_id,
        "titulo": "Cálculo I",
        "descricao_aula": "Limites e derivadas",
        "preco_decimal": 150.0,
        "id_categoria": str(cat_id),
        "id_professor": str(prof_id),
        "status": "disponivel"
    }
    
    payload = {
        "titulo": "Cálculo I",
        "descricao_aula": "Limites e derivadas",
        "preco_decimal": 150.0,
        "id_categoria": str(cat_id),
        "id_professor": str(prof_id)
    }
    
    response = client.post('/api/aulas/', json=payload)
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["titulo"] == "Cálculo I"
    assert data["status"] == "disponivel"
    assert data["id_professor"] == str(prof_id)
    
@patch('app.aulas.routes.mongo')
def test_list_success(mock_mongo, client):
    prof_id = ObjectId()
    cat_id = ObjectId()
    aula_id = ObjectId()
    
    # Aula no banco
    aula_doc = {
        "_id": aula_id,
        "titulo": "Física Quântica",
        "descricao_aula": "Introdução",
        "preco_decimal": 200.0,
        "id_professor": str(prof_id),
        "id_categoria": str(cat_id),
        "status": "disponivel"
    }
    
    
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = [aula_doc]  #Útimo método da cadeia, retorna uma lista iterável
    mock_mongo.db.aulas.find.return_value = mock_cursor #cursor fake
    mock_mongo.db.aulas.count_documents.return_value = 1 #uma Aula
    
    # Mock Professor
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Dr. Albert",
        "email": "albert@example.com",
        "bio": "PhD em Física"
    }
    
    # Mock Categoria
    mock_mongo.db.categorias.find_one.return_value = {
        "_id": cat_id,
        "nome": "Ciências Exatas"
    }
    
    response = client.get('/api/aulas/')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1
    assert len(data["data"]) == 1
    assert "professor" in data["data"][0]
    assert data["data"][0]["professor"]["nome"] == "Dr. Albert"
    assert "categoria" in data["data"][0]
    assert data["data"][0]["categoria"]["nome"] == "Ciências Exatas"
    
@patch('app.aulas.routes.mongo')
def test_get_by_id_success(mock_mongo, client):
    prof_id = ObjectId()
    cat_id = ObjectId()
    aula_id = ObjectId()
    
    # Mock aula
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id,
        "titulo": "Álgebra Linear",
        "descricao_aula": "Matrizes e vetores",
        "preco_decimal": 180.0,
        "id_professor": str(prof_id),
        "id_categoria": str(cat_id),
        "status": "disponivel"
    }
    
    # Mock professor com histórico acad
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Prof. Maria",
        "email": "maria@example.com",
        "bio": "Especialista em matemática",
        "historico_academico_profissional": "Doutorado USP"
    }
    
    # Mock categoria
    mock_mongo.db.categorias.find_one.return_value = {
        "_id": cat_id,
        "nome": "Matemática"
    }
    
    response = client.get(f'/api/aulas/{str(aula_id)}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["_id"] == str(aula_id)
    assert data["titulo"] == "Álgebra Linear"
    assert "professor" in data
    assert data["professor"]["historico_academico_profissional"] == "Doutorado USP"
    assert "categoria" in data
    
@patch('app.aulas.routes.mongo')
def test_update_success(mock_mongo, client):
    aula_id = ObjectId()
    
    # Mock update_one
    mock_result = MagicMock()
    mock_result.matched_count = 1 #doc encontrados
    mock_mongo.db.aulas.update_one.return_value = mock_result
    
    # Mock find_one da aula atualizada 
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id,
        "titulo": "Cálculo II - Atualizado",
        "descricao_aula": "Nova descrição",
        "preco_decimal": 200.0,
        "id_professor": str(ObjectId()),
        "status": "disponivel"
    }
    
    #Json
    payload = {
        "titulo": "Cálculo II - Atualizado",
        "descricao_aula": "Nova descrição"
    }
    
    response = client.put(f'/api/aulas/{str(aula_id)}', json=payload)
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["titulo"] == "Cálculo II - Atualizado"
    assert data["descricao_aula"] == "Nova descrição"

@patch('app.aulas.routes.mongo')
def test_delete_success(mock_mongo, client):
    aula_id = ObjectId()
    
    # Mock delete_one
    mock_result = MagicMock()
    mock_result.deleted_count = 1
    mock_mongo.db.aulas.delete_one.return_value = mock_result
    
    response = client.delete(f'/api/aulas/{str(aula_id)}')
    
    assert response.status_code == 204
    assert response.data == b''

@patch('app.aulas.routes.mongo')
def test_update_status_success(mock_mongo, client):
    aula_id = ObjectId()
    
    # Mock update_one
    mock_result = MagicMock()
    mock_result.matched_count = 1
    mock_mongo.db.aulas.update_one.return_value = mock_result
    
    # Mock insert_one (histórico de status)
    mock_mongo.db.status_aulas.insert_one.return_value = MagicMock(inserted_id=ObjectId())
    
    # Mock find_one final
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id,
        "titulo": "Geometria",
        "id_professor": str(ObjectId()),
        "status": "em andamento"
    }
    
    payload = {"status": "em andamento"}
    
    response = client.put(f'/api/aulas/{str(aula_id)}/status', json=payload)
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "em andamento"