import pytest
from unittest.mock import patch, MagicMock
from bson import ObjectId
from app import create_app
from flask_jwt_extended import create_access_token


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    # Garante que scrub remova senha_hash durante testes
    app.config['SHOW_HASH'] = False
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@patch('app.auth.routes.mongo')
def test_auth_test_endpoint(mock_mongo, client):
    resp = client.get('/api/auth/test')
    assert resp.status_code == 200
    assert resp.get_json().get('msg') == 'Sistema funcionando'

@patch('app.auth.routes.mongo')
def test_auth_test_db_success(mock_mongo, client):
    mock_mongo.db.alunos.count_documents.return_value = 5
    
    # mock Aluno
    mock_mongo.db.alunos.find_one.return_value = {
        '_id': ObjectId(),
        'nome': 'Aluno Exemplo',
        'email': 'aluno@example.com',
        'senha_hash': 'hash'
    }
    
    resp = client.get('/api/auth/test-db')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['alunos_count'] == 5
    assert data['aluno_exemplo'] is not None
    assert data['aluno_exemplo']['nome'] == 'Aluno Exemplo'
    # senha_hash deve ser removido por scrub
    assert 'senha_hash' not in data['aluno_exemplo']

@patch('app.auth.routes.bcrypt')
@patch('app.auth.routes.mongo')
def test_login_aluno_success(mock_mongo, mock_bcrypt, client):
    aluno_id = ObjectId()
    # Encontrar aluno
    mock_mongo.db.alunos.find_one.return_value = {
        '_id': aluno_id,
        'nome': 'João',
        'email': 'joao@example.com',
        'senha_hash': 'hash123'
    }
    
    # bcrypt confere
    mock_bcrypt.checkpw.return_value = True

    payload = { 'email': 'joao@example.com', 'password': 'segredo' }
    resp = client.post('/api/auth/login', json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['tipo'] == 'aluno'
    assert 'access_token' in data
    assert data['user']['_id'] == str(aluno_id)

@patch('app.auth.routes.bcrypt')
@patch('app.auth.routes.mongo')
def test_login_professor_success(mock_mongo, mock_bcrypt, client):
    prof_id = ObjectId()
    mock_mongo.db.alunos.find_one.return_value = None
    # Encontra professor
    mock_mongo.db.professores.find_one.return_value = {
        '_id': prof_id,
        'nome': 'Profa Maria',
        'email': 'maria@example.com',
        'senha_hash': 'hash456'
    }
    mock_bcrypt.checkpw.return_value = True

    payload = { 'email': 'maria@example.com', 'password': 'segredo' }
    resp = client.post('/api/auth/login', json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['tipo'] == 'professor'
    assert 'access_token' in data
    assert data['user']['_id'] == str(prof_id)


def test_verificar_success(app, client):
    with app.app_context():
        claims = {
            'email': 'user@example.com',
            'nome': 'User',
            'tipo': 'aluno'
        }
        token = create_access_token(identity='123', additional_claims=claims)
    headers = { 'Authorization': f'Bearer {token}' }
    
    resp = client.get('/api/auth/verificar', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['email'] == 'user@example.com'
    assert data['nome'] == 'User'
    assert data['tipo'] == 'aluno'


@patch('app.auth.routes.requests.get')
def test_checa_cep_success(mock_get, client):
    # ViaCEP OK
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        'cep': '01001-000',
        'logradouro': 'Praça da Sé',
        'bairro': 'Sé',
        'localidade': 'São Paulo',
        'uf': 'SP'
    }
    mock_get.return_value = fake_resp

    resp = client.get('/api/auth/checa_cep/01001000')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['cep'] == '01001-000'
