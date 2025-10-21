# API de Aulas - Documentação

Este documento descreve as APIs implementadas para o sistema de aulas baseado no diagrama de classes fornecido.

## Estrutura Implementada

### 1. Aulas (`/api/aulas`)
- **POST** `/` - Criar nova aula
- **GET** `/` - Listar aulas (com filtros)
- **GET** `/<id>` - Buscar aula específica
- **PUT** `/<id>` - Atualizar aula
- **DELETE** `/<id>` - Deletar aula
- **PUT** `/<id>/status` - Atualizar status da aula

**Campos da Aula:**
- `titulo` (string, obrigatório)
- `descricao_aula` (string)
- `preco_decimal` (float)
- `id_categoria` (ObjectId, referência para categoria)
- `id_professor` (ObjectId, obrigatório, referência para professor)
- `status` (string: "disponivel", "em andamento", "cancelada", "concluida")

### 2. Categorias (`/api/categorias`)
- **POST** `/` - Criar nova categoria
- **GET** `/` - Listar categorias
- **GET** `/<id>` - Buscar categoria específica
- **PUT** `/<id>` - Atualizar categoria
- **DELETE** `/<id>` - Deletar categoria
- **GET** `/<id>/aulas` - Listar aulas de uma categoria

**Campos da Categoria:**
- `nome` (string, obrigatório, único)

### 3. Agenda (`/api/agenda`)
- **POST** `/` - Criar novo agendamento
- **GET** `/` - Listar agendamentos (com filtros)
- **GET** `/<id>` - Buscar agendamento específico
- **PUT** `/<id>` - Atualizar agendamento
- **DELETE** `/<id>` - Deletar agendamento
- **PUT** `/<id>/status` - Atualizar status do agendamento

**Campos da Agenda:**
- `id_aluno` (ObjectId, obrigatório)
- `id_professor` (ObjectId, obrigatório)
- `id_aula` (ObjectId, obrigatório)
- `data_hora` (datetime, obrigatório)
- `status` (string: "agendada", "confirmada", "cancelada", "concluida", "ausente")
- `observacoes` (string, opcional)

### 4. Avaliações (`/api/avaliacoes`)
- **POST** `/` - Criar nova avaliação
- **GET** `/` - Listar avaliações (com filtros)
- **GET** `/<id>` - Buscar avaliação específica
- **PUT** `/<id>` - Atualizar avaliação
- **DELETE** `/<id>` - Deletar avaliação
- **GET** `/professor/<id>/stats` - Estatísticas de avaliações do professor
- **GET** `/aula/<id>/stats` - Estatísticas de avaliações da aula

**Campos da Avaliação:**
- `id_aluno` (ObjectId, obrigatório)
- `id_aula` (ObjectId, obrigatório)
- `id_prof` (ObjectId, obrigatório)
- `nota` (float, obrigatório, 0-10)
- `texto` (string, opcional)

## Validações Implementadas

### Aulas
- Professor deve existir
- Categoria deve existir (se fornecida)
- Preço deve ser um número válido
- Status deve ser um dos valores permitidos

### Categorias
- Nome é obrigatório e único
- Não pode deletar categoria que possui aulas

### Agenda
- Aluno, professor e aula devem existir
- Aula deve pertencer ao professor
- Não pode haver conflitos de horário para professor ou aluno
- Data deve estar em formato válido

### Avaliações
- Aluno, professor e aula devem existir
- Aula deve pertencer ao professor
- Aluno deve ter participado da aula (agendamento concluído)
- Nota deve estar entre 0 e 10
- Um aluno só pode avaliar uma aula uma vez

## Filtros Disponíveis

### Aulas
- `q` - Busca por título ou descrição
- `categoria` - Filtrar por categoria
- `professor` - Filtrar por professor
- `status` - Filtrar por status

### Agenda
- `aluno` - Filtrar por aluno
- `professor` - Filtrar por professor
- `aula` - Filtrar por aula
- `status` - Filtrar por status
- `data_inicio` - Filtrar por data inicial
- `data_fim` - Filtrar por data final

### Avaliações
- `aluno` - Filtrar por aluno
- `professor` - Filtrar por professor
- `aula` - Filtrar por aula
- `nota_min` - Nota mínima
- `nota_max` - Nota máxima

## Índices MongoDB

Foram criados índices otimizados para:
- Busca por texto em aulas
- Filtros por relacionamentos (professor, categoria, aluno)
- Ordenação por data de criação
- Prevenção de conflitos de horário
- Unicidade de avaliações por aluno/aula

## Exemplos de Uso

### Criar uma aula
```json
POST /api/aulas
{
  "titulo": "Aula de Python",
  "descricao_aula": "Aprenda os fundamentos do Python",
  "preco_decimal": 50.00,
  "id_categoria": "64f1a2b3c4d5e6f7a8b9c0d1",
  "id_professor": "64f1a2b3c4d5e6f7a8b9c0d2"
}
```

### Agendar uma aula
```json
POST /api/agenda
{
  "id_aluno": "64f1a2b3c4d5e6f7a8b9c0d3",
  "id_professor": "64f1a2b3c4d5e6f7a8b9c0d2",
  "id_aula": "64f1a2b3c4d5e6f7a8b9c0d4",
  "data_hora": "2024-01-15T14:00:00Z"
}
```

### Avaliar uma aula
```json
POST /api/avaliacoes
{
  "id_aluno": "64f1a2b3c4d5e6f7a8b9c0d3",
  "id_aula": "64f1a2b3c4d5e6f7a8b9c0d4",
  "id_prof": "64f1a2b3c4d5e6f7a8b9c0d2",
  "nota": 9.5,
  "texto": "Excelente aula, muito didática!"
}
```
