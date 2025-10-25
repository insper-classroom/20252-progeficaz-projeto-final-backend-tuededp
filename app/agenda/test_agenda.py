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

@patch('app.agenda.routes.mongo')
def test_create_success(mock_mongo, client):
    # IDs fictícios
    aluno_id = ObjectId()
    prof_id = ObjectId()
    aula_id = ObjectId()
    
    # Quando o programa chamar 'mongo.db.alunos.find_one(...), irá retornar esses dicionários
    # Simula que o banco de dados tem essas pessoas
    mock_mongo.db.alunos.find_one.return_value = {"_id": aluno_id, "nome": "João"}
    mock_mongo.db.professores.find_one.return_value = {"_id": prof_id, "nome": "Maria"}
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id, 
        "titulo": "Matemática",
        "id_professor": prof_id
    }
    
    # simula a inserção no mongo
    inserted = ObjectId()
    mock_mongo.db.agenda.insert_one.return_value = MagicMock(inserted_id=inserted)
   
    final_doc = {
        "_id": inserted,
        "id_aluno": str(aluno_id),
        "id_professor": str(prof_id),
        "id_aula": str(aula_id),
        "data_hora": datetime(2025, 12, 1, 10, 0, tzinfo=timezone.utc),
        "status": "agendada"
    }
    # Conflitos: duas primeiras chamadas retornam None e a última retorna a aula agendada
    mock_mongo.db.agenda.find_one.side_effect = [None, None, final_doc]
    
    # Cria o Json
    payload = {
        "id_aluno": str(aluno_id),
        "id_professor": str(prof_id),
        "id_aula": str(aula_id),
        "data_hora": "2025-12-01T10:00:00Z"
    }
    
    response = client.post('/api/agenda/', json=payload)
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "agendada"
    assert data["id_aluno"] == str(aluno_id)
    
@patch('app.agenda.routes.mongo')
def test_list_success(mock_mongo, client):
    # IDs fictícios
    aluno_id = ObjectId()
    prof_id = ObjectId()
    aula_id = ObjectId()
    agenda_id = ObjectId()
    
    # Agendamento que esta no banco
    agenda = {
        "_id": agenda_id,
        "id_aluno": str(aluno_id),
        "id_professor": str(prof_id),
        "id_aula": str(aula_id),
        "data_hora": datetime(2025, 12, 1, 10, 0, tzinfo=timezone.utc),
        "status": "agendada"
    }
    
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = [agenda] #Útimo método da cadeia, retorna uma lista iterável
    mock_mongo.db.agenda.find.return_value = mock_cursor #cursor fake
    mock_mongo.db.agenda.count_documents.return_value = 1 #um agendamento
    
    # Mock Aluno
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": aluno_id, 
        "nome": "João Silva", 
        "email": "joao@example.com", 
        "telefone": "11999999999"
    }
    # Mock Professor
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id, 
        "nome": "Maria Santos", 
        "email": "maria@example.com", 
        "telefone": "11888888888"
    }
    # Mock Aula
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id, 
        "titulo": "Matemática Avançada", 
        "descricao_aula": "Álgebra Linear", 
        "preco_decimal": 150.0
    }
    
    response = client.get('/api/agenda/')
    
    assert response.status_code == 200
    data = response.get_json()
    # verificações (aluno, professor, aula e se tem um agendamento)
    assert data["total"] == 1 
    assert len(data["data"]) == 1
    assert "aluno" in data["data"][0]
    assert data["data"][0]["aluno"]["nome"] == "João Silva"
    assert "professor" in data["data"][0]
    assert data["data"][0]["professor"]["nome"] == "Maria Santos"
    assert "aula" in data["data"][0]
    assert data["data"][0]["aula"]["titulo"] == "Matemática Avançada"
    
@patch('app.agenda.routes.mongo')
def test_get_by_id_success(mock_mongo, client):
    # IDs fictícios
    aluno_id = ObjectId()
    prof_id = ObjectId()
    aula_id = ObjectId()
    agenda_id = ObjectId()
    
    # Mock agenda
    mock_mongo.db.agenda.find_one.return_value = {
        "_id": agenda_id,
        "id_aluno": str(aluno_id),
        "id_professor": str(prof_id),
        "id_aula": str(aula_id),
        "data_hora": datetime(2025, 12, 1, 14, 30, tzinfo=timezone.utc),
        "status": "confirmada",
        "observacoes": "Trazer calculadora"
    }
    
    # mocks (aluno, professor, aula)
    mock_mongo.db.alunos.find_one.return_value = {
        "_id": aluno_id,
        "nome": "Pedro Costa",
        "email": "pedro@example.com",
        "telefone": "11777777777",
        "cpf": "12345678900"
    }
    mock_mongo.db.professores.find_one.return_value = {
        "_id": prof_id,
        "nome": "Ana Paula",
        "email": "ana@example.com",
        "telefone": "11666666666",
        "especialidade": "Matemática"
    }
    mock_mongo.db.aulas.find_one.return_value = {
        "_id": aula_id,
        "titulo": "Cálculo I",
        "descricao_aula": "Limites e Derivadas",
        "preco_decimal": 200.0,
        "id_professor": str(prof_id)
    }
    
    response = client.get(f'/api/agenda/{str(agenda_id)}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["_id"] == str(agenda_id)
    assert data["status"] == "confirmada"
    # Verificação de objetos COMPLETOS (não só nome/email/telefone), para aluno, professor e aula
    assert "aluno" in data
    assert data["aluno"]["cpf"] == "12345678900"
    assert "professor" in data
    assert data["professor"]["especialidade"] == "Matemática"
    assert "aula" in data
    assert data["aula"]["preco_decimal"] == 200.0
    
@patch('app.agenda.routes.mongo')
def test_update_success(mock_mongo, client):
    # ID fictício da agenda
    agenda_id = ObjectId()
    
    # Mock update_one
    mock_result = MagicMock()
    mock_result.matched_count = 1 # quantos documentos foram encontrados 
    mock_mongo.db.agenda.update_one.return_value = mock_result
    
    # Mock find_one do documento atualizado
    mock_mongo.db.agenda.find_one.return_value = {
        "_id": agenda_id,
        "id_aluno": str(ObjectId()),
        "id_professor": str(ObjectId()),
        "id_aula": str(ObjectId()),
        "data_hora": datetime(2025, 12, 2, 16, 0, tzinfo=timezone.utc),
        "status": "confirmada",
        "observacoes": "Aula remarcada"
    }
    
    # Json que será enviado para o 
    payload = {
        "status": "confirmada",
        "observacoes": "Aula remarcada"
    }
    
    response = client.put(f'/api/agenda/{str(agenda_id)}', json=payload)
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "confirmada"
    assert data["observacoes"] == "Aula remarcada"
    
@patch('app.agenda.routes.mongo')
def test_delete_success(mock_mongo, client):
    # ID fictício da agenda
    agenda_id = ObjectId()
    
    # Mock delete_one
    mock_result = MagicMock()
    mock_result.deleted_count = 1
    mock_mongo.db.agenda.delete_one.return_value = mock_result
    
    response = client.delete(f'/api/agenda/{str(agenda_id)}')
    
    assert response.status_code == 204
    assert response.data == b''  # Sem corpo na resposta
    
@patch('app.agenda.routes.mongo')
def test_update_status_success(mock_mongo, client):
    # ID fictício da agenda
    agenda_id = ObjectId()
    
    # Mock update_one
    mock_result = MagicMock()
    mock_result.matched_count = 1
    mock_mongo.db.agenda.update_one.return_value = mock_result
    
    # Mock final
    mock_mongo.db.agenda.find_one.return_value = {
        "_id": agenda_id,
        "id_aluno": str(ObjectId()),
        "id_professor": str(ObjectId()),
        "id_aula": str(ObjectId()),
        "data_hora": datetime(2025, 12, 1, 10, 0, tzinfo=timezone.utc),
        "status": "concluida" #Muda o status
    }
    
    payload = {"status": "concluida"}
    
    response = client.put(f'/api/agenda/{str(agenda_id)}/status', json=payload)
    
    # Verificação
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "concluida"