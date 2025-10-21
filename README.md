# 🧠 Estudaí — Backend

[![Status](https://img.shields.io/badge/status-development-orange)]()
[![Python](https://img.shields.io/badge/python-3.12+-blue)]()
[![License](https://img.shields.io/badge/license-academic-lightgrey)]()

> Backend do **Estudaí**, plataforma que conecta veteranos (monitores / alunos-destaque) com alunos universitários para aulas particulares acessíveis.  
> API REST construída em **Flask** e **MongoDB**.

---

## 📘 Sobre o Projeto
O backend fornece rotas REST para **gerenciar usuários (alunos e professores)**, realizando operações CRUD completas, com suporte a busca, paginação e filtros dinâmicos.  
Também serve como base para o futuro **agente inteligente**, responsável por interpretar descrições de matérias e sugerir professores correspondentes.

---

## ⚙️ Tecnologias Utilizadas
- 🐍 **Python 3.12+**
- 🔥 **Flask**
- 🍃 **MongoDB**
- 🔐 **bcrypt** — hash seguro de senhas
- 🌐 **Flask-CORS** — integração com frontend React
- 📦 **PyMongo** — driver de conexão com MongoDB

---

## 🗂️ Estrutura do Projeto

```bash
app/
├── alunos/                   # Rotas e lógica dos alunos
│   └── __init__.py
├── professores/              # Rotas e lógica dos professores
│   └── __init__.py
├── extensions.py             # Configuração Mongo e CORS
├── utils.py                  # Funções auxiliares (hash, datas, scrub)
└── __init__.py               # Inicialização Flask App
app.py                        # Ponto de entrada principal
requirements.txt              # Dependências do projeto
.env                          # Variáveis de ambiente
README.md                     # Documentação




