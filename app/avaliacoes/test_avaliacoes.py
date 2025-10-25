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

@patch('app.avaliacoes.routes.mongo')
def test_create_success(mock_mongo, client):
    aluno_id = ObjectId()
    aula_id = ObjectId()
    prof_id = ObjectId()
    
    # Mock aluno existe
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": aluno_id,
        "nome": "João Silva"
    }
    
    # Mock professor existe
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Prof. Maria"
    }
    
    # Mock aula existe e pertence ao professor
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id,
        "titulo": "Cálculo I",
        "id_professor": prof_id
    }
    
    # Ordem de chamadas na rota:
    # 1) avaliacoes.find_one (duplicata)
    # 2) agenda.find_one (participação)
    # 3) avaliacoes.find_one (busca final)
    # Portanto configuramos side_effect para [None, final_doc]
    mock_mongo.db.avaliacoes.find_one.side_effect = [None]
    mock_mongo.db.agenda.find_one.return_value = {
        "_id": ObjectId(),
        "id_aluno": aluno_id,
        "id_aula": aula_id,
        "id_professor": prof_id,
        "status": "concluida"
    }
    
    # Mock insert
    inserted_id = ObjectId()
    mock_mongo.db.avaliacoes.insert_one.return_value = MagicMock(inserted_id=inserted_id)
    
    final_doc = {
        "_id": inserted_id,
        "id_aluno": str(aluno_id),
        "id_prof": str(prof_id),
        "id_aula": str(aula_id),
        "nota": 9.5,
        "texto": "Excelente aula!"
    }
    
    # Atualiza side_effect para incluir o doc final na 2ª chamada
    mock_mongo.db.avaliacoes.find_one.side_effect = [None, final_doc]
    
    payload = {
        "id_aluno": str(aluno_id),
        "id_prof": str(prof_id),
        "id_aula": str(aula_id),
        "nota": 9.5,
        "texto": "Excelente aula!"
    }
    
    response = client.post('/api/avaliacoes/', json=payload)
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["nota"] == 9.5
    assert data["texto"] == "Excelente aula!"
    assert data["id_aluno"] == str(aluno_id)
    
@patch('app.avaliacoes.routes.mongo')
def test_list_success(mock_mongo, client):
    aluno_id = ObjectId()
    prof_id = ObjectId()
    aula_id = ObjectId()
    avaliacao_id = ObjectId()
    
    # Avaliação no banco
    avaliacao_doc = {
        "_id": avaliacao_id,
        "id_aluno": str(aluno_id),
        "id_prof": str(prof_id),
        "id_aula": str(aula_id),
        "nota": 8.5,
        "texto": "Ótima didática"
    }
    
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = [avaliacao_doc]
    mock_mongo.db.avaliacoes.find.return_value = mock_cursor
    mock_mongo.db.avaliacoes.count_documents.return_value = 1
    
    # Mock aluno (só nome e email)
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": aluno_id,
        "nome": "Pedro Costa",
        "email": "pedro@example.com"
    }
    
    # Mock professor (só nome e email)
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Prof. Ana",
        "email": "ana@example.com"
    }
    
    # Mock aula (título e descrição)
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id,
        "titulo": "Física Quântica",
        "descricao_aula": "Introdução à mecânica quântica"
    }
    
    response = client.get('/api/avaliacoes/')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1
    assert len(data["data"]) == 1
    assert data["data"][0]["nota"] == 8.5
    assert "aluno" in data["data"][0]
    assert data["data"][0]["aluno"]["nome"] == "Pedro Costa"
    assert "professor" in data["data"][0]
    assert data["data"][0]["professor"]["nome"] == "Prof. Ana"
    assert "aula" in data["data"][0]
    assert data["data"][0]["aula"]["titulo"] == "Física Quântica"
    
@patch('app.avaliacoes.routes.mongo')
def test_get_by_id_success(mock_mongo, client):
    aluno_id = ObjectId()
    prof_id = ObjectId()
    aula_id = ObjectId()
    avaliacao_id = ObjectId()
    
    # Mock avaliação
    mock_mongo.db.avaliacoes.find_one.return_value = {
        "_id": avaliacao_id,
        "id_aluno": str(aluno_id),
        "id_prof": str(prof_id),
        "id_aula": str(aula_id),
        "nota": 10.0,
        "texto": "Perfeito!"
    }
    
    # Mock aluno COMPLETO
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": aluno_id,
        "nome": "Lucas Oliveira",
        "email": "lucas@example.com",
        "telefone": "11999999999",
        "cpf": "12345678900"
    }
    
    # Mock professor COMPLETO
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Dr. Roberto",
        "email": "roberto@example.com",
        "bio": "PhD em Matemática",
        "especialidade": "Cálculo"
    }
    
    # Mock aula COMPLETA
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id,
        "titulo": "Álgebra Abstrata",
        "descricao_aula": "Grupos e anéis",
        "preco_decimal": 250.0,
        "id_professor": str(prof_id)
    }
    
    response = client.get(f'/api/avaliacoes/{str(avaliacao_id)}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["_id"] == str(avaliacao_id)
    assert data["nota"] == 10.0
    assert "aluno" in data
    assert data["aluno"]["cpf"] == "12345678900"  # Campo extra que não vem no list
    assert "professor" in data
    assert data["professor"]["especialidade"] == "Cálculo"
    assert "aula" in data
    assert data["aula"]["preco_decimal"] == 250.0
    
@patch('app.avaliacoes.routes.mongo')
def test_update_success(mock_mongo, client):
    avaliacao_id = ObjectId()
    
    # Mock update_one
    mock_result = MagicMock()
    mock_result.matched_count = 1
    mock_mongo.db.avaliacoes.update_one.return_value = mock_result
    
    # Mock find_one doc atualizado
    mock_mongo.db.avaliacoes.find_one.return_value = {
        "_id": avaliacao_id,
        "id_aluno": str(ObjectId()),
        "id_prof": str(ObjectId()),
        "id_aula": str(ObjectId()),
        "nota": 9.0,
        "texto": "Texto atualizado - muito bom!"
    }
    
    payload = {
        "nota": 9.0,
        "texto": "Texto atualizado - muito bom!"
    }
    
    response = client.put(f'/api/avaliacoes/{str(avaliacao_id)}', json=payload)
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["nota"] == 9.0
    assert data["texto"] == "Texto atualizado - muito bom!"

@patch('app.avaliacoes.routes.mongo')
def test_delete_success(mock_mongo, client):
    avaliacao_id = ObjectId()
    
    # Mock delete_one
    mock_result = MagicMock()
    mock_result.deleted_count = 1
    mock_mongo.db.avaliacoes.delete_one.return_value = mock_result
    
    response = client.delete(f'/api/avaliacoes/{str(avaliacao_id)}')
    
    assert response.status_code == 204
    assert response.data == b''

@patch('app.avaliacoes.routes.mongo')
def test_get_professor_stats_success(mock_mongo, client):
    prof_id = ObjectId()
    
    # Mock professor existe
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Prof. Carlos",
        "email": "carlos@example.com"
    }
    
    # Mock aggregate (estatísticas)
    mock_mongo.db.avaliacoes.aggregate.return_value = [{
        "_id": None,
        "total_avaliacoes": 5,
        "nota_media": 8.6,
        "nota_min": 7.0,
        "nota_max": 10.0
    }]
    
    response = client.get(f'/api/avaliacoes/professor/{str(prof_id)}/stats')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_avaliacoes"] == 5
    assert data["nota_media"] == 8.6
    assert data["nota_min"] == 7.0
    assert data["nota_max"] == 10.0
    assert "professor" in data
    assert data["professor"]["nome"] == "Prof. Carlos"

@patch('app.avaliacoes.routes.mongo')
def test_get_aula_stats_success(mock_mongo, client):
    aula_id = ObjectId()
    
    # Mock aula existe
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id,
        "titulo": "Geometria Analítica",
        "descricao_aula": "Vetores e matrizes"
    }
    
    # Mock aggregate (estatísticas)
    mock_mongo.db.avaliacoes.aggregate.return_value = [{
        "_id": None,
        "total_avaliacoes": 10,
        "nota_media": 9.2,
        "nota_min": 8.0,
        "nota_max": 10.0
    }]
    
    response = client.get(f'/api/avaliacoes/aula/{str(aula_id)}/stats')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_avaliacoes"] == 10
    assert data["nota_media"] == 9.2
    assert data["nota_min"] == 8.0
    assert data["nota_max"] == 10.0
    assert "aula" in data
    assert data["aula"]["titulo"] == "Geometria Analítica"

@patch('app.avaliacoes.routes.mongo')
def test_get_professor_stats_empty(mock_mongo, client):
    prof_id = ObjectId()
    
    # Mock professor existe
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Prof. Novo",
        "email": "novo@example.com"
    }
    
    # Mock aggregate retorna lista vazia (nenhuma avaliação)
    mock_mongo.db.avaliacoes.aggregate.return_value = []
    
    response = client.get(f'/api/avaliacoes/professor/{str(prof_id)}/stats')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["total_avaliacoes"] == 0
    assert data["nota_media"] == 0
    assert data["nota_min"] == 0
    assert data["nota_max"] == 0
    assert "professor" in data