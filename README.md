# 🧠 Estudaí — Backend (Flask API)

[![Status](https://img.shields.io/badge/status-development-orange?style=for-the-badge)]()
[![Python](https://img.shields.io/badge/python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)]()
[![Flask](https://img.shields.io/badge/Flask-2.3.0-black?style=for-the-badge&logo=flask&logoColor=white)]()
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-4DB33D?style=for-the-badge&logo=mongodb&logoColor=white)]()
[![License](https://img.shields.io/badge/License-Academic-lightgrey?style=for-the-badge)]()

> Backend do **Estudaí**, plataforma que conecta **veteranos (monitores / alunos-destaque)** com **alunos universitários** para aulas particulares acessíveis.  
> API REST construída com **Flask**, **MongoDB** e **arquitetura modular**, aplicando boas práticas de engenharia de software e metodologias ágeis.
> > Parte do **Projeto 3 — Programação Eficaz - Insper - Segundo Período**.


---

## 📘 Sobre o Projeto

O backend é responsável por toda a **lógica de negócio e persistência de dados** do Estudaí.  
Oferece rotas **RESTful** para **cadastro, autenticação e gerenciamento de usuários, aulas, categorias, avaliações e agenda**, além da integração com serviços externos como o **ViaCEP**.

O sistema também prevê a implementação de um **agente inteligente**, que futuramente recomendará professores com base em descrições textuais e preferências dos alunos.

---

## 🎯 Objetivos

### 🎓 Objetivo Geral
Desenvolver uma **API segura e escalável** para intermediar a comunicação entre frontend React e banco de dados MongoDB.

### 🧩 Objetivos Específicos
- Implementar CRUD completo para alunos e professores.  
- Desenvolver rotas de agenda, aulas e avaliações.  
- Garantir autenticação segura com JWT e bcrypt.  
- Fornecer endpoints para busca, filtros e estatísticas.  
- Integrar com API externa ViaCEP.  
- Aplicar metodologia ágil (Kanban) no desenvolvimento colaborativo.

---

## ⚙️ Tecnologias Utilizadas

| Categoria | Tecnologias |
|------------|-------------|
| **Linguagem** | Python 3.12+ |
| **Framework** | Flask |
| **Banco de Dados** | MongoDB Atlas |
| **ORM / Driver** | PyMongo |
| **Segurança** | bcrypt, JWT |
| **Integração** | Flask-CORS |
| **Ambiente** | dotenv |
| **Testes** | Insomnia / Postman |
| **Versionamento** | Git e GitHub |

---

## 🗂️ Estrutura do Projeto

```bash
app/
│
├── __pycache__/                # Cache interno do Python
│
├── agenda/                     # Módulo de rotas e lógica da agenda
│   ├── __init__.py
│   └── routes.py
│
├── alunos/                     # Módulo de rotas e lógica dos alunos
│   ├── __init__.py
│   └── routes.py
│
├── aulas/                      # Módulo de rotas e lógica das aulas
│   ├── __init__.py
│   └── routes.py
│
├── auth/                       # Módulo de autenticação e login
│   ├── __init__.py
│   └── routes.py
│
├── avaliacoes/                 # Módulo de avaliações e notas
│   ├── __init__.py
│   └── routes.py
│
├── categorias/                 # Módulo de categorias de aulas
│   ├── __init__.py
│   └── routes.py
│
├── chats/                      # Módulo de chat entre aluno e professor
│   ├── __init__.py
│   └── routes.py
│
├── professores/                # Módulo de rotas e lógica dos professores
│   ├── __init__.py
│   └── routes.py
│
├── uploads/                    # Armazenamento de arquivos enviados
│   ├── __init__.py
│   └── handlers.py
│
├── __init__.py                 # Inicialização do app Flask
├── extensions.py               # Configurações (MongoDB, JWT, CORS)
├── utils.py                    # Funções utilitárias (hash, validação, sanitização)
│
venv/                           # Ambiente virtual Python
│
.gitignore                      # Arquivos e pastas ignorados pelo Git
.env                            # Variáveis de ambiente (não versionado)
app.py                          # Ponto de entrada principal do servidor Flask
AULAS.md                        # Documentação específica de aulas
README.md                       # Documentação geral do backend
requirements.txt                # Dependências do projeto
test.ps1                        # Script PowerShell para testes locais

```
## 📄 Acesso ao documento do projeto
https://docs.google.com/document/d/1C1V_qLk0f_oySNz3rmSsapQO2a3BLTWCD8VKug_Kxy8/edit?usp=sharing

## 👨‍💻 Equipe de Desenvolvimento

| Nome |
|------|
| Gabriel Rosa | 
| João Pedro Vivaqua |
| João Pedro Murbach |
| Lucas Bressanin |
| Murilo Godoy |
| Vinicius Oehlmann |
| Victor Pimenta |

## 📄 Acesso ao documento do projeto
http://54.196.232.66/8000/api





