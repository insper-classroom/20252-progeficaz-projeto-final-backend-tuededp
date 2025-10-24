#!/usr/bin/env pwsh
# Script para rodar testes do projeto
# Uso: .\test.ps1 [argumentos do pytest]
# Exemplos:
#   .\test.ps1                    # roda todos os testes
#   .\test.ps1 app\alunos         # roda só testes de alunos
#   .\test.ps1 -v                 # roda com verbose

# Define PYTHONPATH para a raiz do projeto
$env:PYTHONPATH = $PWD

# Ativa a venv e roda pytest com os argumentos passados
& .\.venv\Scripts\python.exe -m pytest $args
