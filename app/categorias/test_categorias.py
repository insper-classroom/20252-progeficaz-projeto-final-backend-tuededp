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

@patch('app.categorias.routes.mongo')
def test_create_success(mock_mongo, client):
    cat_id = ObjectId()
    
    # Mock Categoria
    mock_mongo.db.categorias.insert_one.return_value = MagicMock(inserted_id=cat_id)
    mock_mongo.db.categorias.find_one.return_value = {
        "_id": cat_id,
        "nome": "Exatas"
    }
    
    payload = {"nome": "Exatas"}
    resp = client.post('/api/categorias/', json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["_id"] == str(cat_id)
    assert data["nome"] == "Exatas"


@patch('app.categorias.routes.mongo')
def test_list_success(mock_mongo, client):
    cat_id = ObjectId()
    # Cadeia do cursor
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = [{
        "_id": cat_id,
        "nome": "Humanas"
    }]
    mock_mongo.db.categorias.find.return_value = mock_cursor
    mock_mongo.db.categorias.count_documents.return_value = 1
    mock_mongo.db.aulas.count_documents.return_value = 3

    resp = client.get('/api/categorias/')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["nome"] == "Humanas"
    assert body["data"][0]["aulas_count"] == 3


@patch('app.categorias.routes.mongo')
def test_get_by_id_success(mock_mongo, client):
    cat_id = ObjectId()
    mock_mongo.db.categorias.find_one.return_value = {
        "_id": cat_id,
        "nome": "Biológicas"
    }
    mock_mongo.db.aulas.count_documents.return_value = 2
    mock_aulas_cursor = MagicMock()
    mock_aulas_cursor.limit.return_value = [
        {"_id": ObjectId(), "titulo": "Anatomia", "preco_decimal": 120.0, "status": "disponivel"},
        {"_id": ObjectId(), "titulo": "Fisiologia", "preco_decimal": 150.0, "status": "disponivel"},
    ]
    mock_mongo.db.aulas.find.return_value = mock_aulas_cursor

    resp = client.get(f'/api/categorias/{str(cat_id)}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["_id"] == str(cat_id)
    assert data["nome"] == "Biológicas"
    assert data["aulas_count"] == 2
    assert len(data["aulas"]) == 2
    assert data["aulas"][0]["titulo"] == "Anatomia"


@patch('app.categorias.routes.mongo')
def test_update_success(mock_mongo, client):
    cat_id = ObjectId()
    mock_res = MagicMock()
    mock_res.matched_count = 1
    mock_mongo.db.categorias.update_one.return_value = mock_res
    mock_mongo.db.categorias.find_one.return_value = {
        "_id": cat_id,
        "nome": "Exatas Atualizada"
    }
    payload = {"nome": "  Exatas Atualizada  "}
    resp = client.put(f'/api/categorias/{str(cat_id)}', json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["nome"] == "Exatas Atualizada"


@patch('app.categorias.routes.mongo')
def test_delete_success(mock_mongo, client):
    cat_id = ObjectId()
    # Sem aulas vinculadas
    mock_mongo.db.aulas.count_documents.return_value = 0
    mock_del = MagicMock()
    mock_del.deleted_count = 1
    mock_mongo.db.categorias.delete_one.return_value = mock_del
    resp = client.delete(f'/api/categorias/{str(cat_id)}')
    assert resp.status_code == 204
    assert resp.data == b''


@patch('app.categorias.routes.mongo')
def test_get_aulas_by_categoria_success(mock_mongo, client):
    cat_id = ObjectId()
    prof_id = ObjectId()
    
    mock_mongo.db.categorias.find_one.return_value = {
        "_id": cat_id,
        "nome": "Artes"
    }
    
    aula_doc = {
        "_id": ObjectId(),
        "titulo": "Pintura I",
        "descricao_aula": "Técnicas básicas",
        "preco_decimal": 99.9,
        "status": "disponivel",
        "id_professor": str(prof_id)
    }
    
    aulas_cursor = MagicMock()
    aulas_cursor.sort.return_value = aulas_cursor
    aulas_cursor.skip.return_value = aulas_cursor
    aulas_cursor.limit.return_value = [aula_doc]
    mock_mongo.db.aulas.find.return_value = aulas_cursor
    mock_mongo.db.aulas.count_documents.return_value = 1
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Prof. Tarsila",
        "email": "tarsila@example.com",
        "bio": "Artista e professora"
    }

    resp = client.get(f'/api/categorias/{str(cat_id)}/aulas')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["categoria"]["_id"] == str(cat_id)
    assert data["total"] == 1
    assert len(data["data"]) == 1
    aula_out = data["data"][0]
    assert aula_out["titulo"] == "Pintura I"
    assert "professor" in aula_out
    assert aula_out["professor"]["nome"] == "Prof. Tarsila"
