from flask import Flask, request, jsonify

app = Flask(__name__)

app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui'


@app.route('/')
def index():
    """Página inicial da API"""
    return jsonify({
        'message': 'API Flask funcionando!',
        'status': 'success',
        'version': '1.0.0'
    })

if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000
    )