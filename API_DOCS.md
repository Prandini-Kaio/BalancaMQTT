# Documentação da API REST - Backend

## Visão Geral

O backend expõe uma API REST que fornece dados dos sensores de peso em tempo real. A API está disponível em `http://localhost:5000` por padrão.

## Endpoints

### 1. Health Check
**GET** `/api/health`

Verifica se o servidor está ativo.

**Resposta:**
```json
{
  "status": "ok",
  "message": "Backend ativo"
}
```

---

### 2. Listar Prateleiras
**GET** `/api/prateleiras`

Retorna lista de todas as prateleiras cadastradas.

**Resposta:**
```json
[
  {
    "prateleira_id": 1,
    "num_sensores": 1,
    "sensores": [1]
  },
  {
    "prateleira_id": 2,
    "num_sensores": 2,
    "sensores": [1, 2]
  }
]
```

---

### 3. Obter Prateleira
**GET** `/api/prateleiras/{prateleira_id}`

Retorna dados detalhados de uma prateleira específica.

**Parâmetros:**
- `prateleira_id` (int) - ID da prateleira

**Resposta:**
```json
{
  "prateleira_id": 1,
  "num_sensores": 1,
  "sensores": [
    {
      "prateleira_id": 1,
      "sensor_id": 1,
      "peso_atual": 4500.50,
      "peso_inicial": 7500.00,
      "percentual_restante": 60.0,
      "timestamp": "2024-01-15 14:30:25",
      "timestamp_recebimento": "2024-01-15T14:30:25.123456"
    }
  ]
}
```

**Erro 404:**
```json
{
  "erro": "Prateleira não encontrada"
}
```

---

### 4. Listar Sensores
**GET** `/api/sensores`

Retorna lista de todos os sensores de todas as prateleiras.

**Resposta:**
```json
[
  {
    "prateleira_id": 1,
    "sensor_id": 1,
    "peso_atual": 4500.50,
    "peso_inicial": 7500.00,
    "percentual_restante": 60.0,
    "timestamp": "2024-01-15 14:30:25",
    "timestamp_recebimento": "2024-01-15T14:30:25.123456"
  },
  {
    "prateleira_id": 2,
    "sensor_id": 1,
    "peso_atual": 3200.00,
    "peso_inicial": 8000.00,
    "percentual_restante": 40.0,
    "timestamp": "2024-01-15 14:30:28",
    "timestamp_recebimento": "2024-01-15T14:30:28.123456"
  }
]
```

---

### 5. Obter Sensor
**GET** `/api/sensores/{prateleira_id}/{sensor_id}`

Retorna dados detalhados de um sensor específico, incluindo histórico de leituras.

**Parâmetros:**
- `prateleira_id` (int) - ID da prateleira
- `sensor_id` (int) - ID do sensor

**Resposta:**
```json
{
  "prateleira_id": 1,
  "sensor_id": 1,
  "peso_atual": 4500.50,
  "peso_inicial": 7500.00,
  "percentual_restante": 60.0,
  "timestamp": "2024-01-15 14:30:25",
  "timestamp_recebimento": "2024-01-15T14:30:25.123456",
  "historico": [
    {
      "peso": 4500.50,
      "percentual": 60.0,
      "timestamp": "2024-01-15 14:30:25"
    },
    {
      "peso": 4800.00,
      "percentual": 64.0,
      "timestamp": "2024-01-15 14:30:22"
    }
  ]
}
```

**Erro 404:**
```json
{
  "erro": "Sensor não encontrado"
}
```

---

### 6. Listar Alertas
**GET** `/api/alertas`

Retorna lista de alertas ativos (sensores com peso crítico).

**Resposta:**
```json
[
  {
    "prateleira_id": 1,
    "sensor_id": 1,
    "peso_atual": 1200.00,
    "peso_critico": 1500.00,
    "tipo": "REPOSICAO_URGENTE",
    "mensagem": "⚠️ PESO CRÍTICO! Reposição necessária na Prateleira 1, Sensor 1",
    "timestamp": "2024-01-15 14:35:10",
    "timestamp_recebimento": "2024-01-15T14:35:10.123456"
  }
]
```

---

### 7. Estatísticas
**GET** `/api/estatisticas`

Retorna estatísticas gerais do sistema.

**Resposta:**
```json
{
  "leituras_recebidas": 150,
  "alertas_recebidos": 5,
  "alertas_ativos": 2,
  "total_prateleiras": 3,
  "total_sensores": 4
}
```

---

## Exemplos de Uso

### cURL

```bash
# Health check
curl http://localhost:5000/api/health

# Listar prateleiras
curl http://localhost:5000/api/prateleiras

# Obter prateleira específica
curl http://localhost:5000/api/prateleiras/1

# Listar sensores
curl http://localhost:5000/api/sensores

# Obter sensor específico
curl http://localhost:5000/api/sensores/1/1

# Listar alertas
curl http://localhost:5000/api/alertas

# Estatísticas
curl http://localhost:5000/api/estatisticas
```

---

## Notas

- Todos os endpoints retornam dados em formato JSON
- Os timestamps estão no formato ISO 8601
- O histórico de leituras mantém as últimas 100 leituras por sensor
- Os alertas são removidos automaticamente quando o peso volta ao normal
- A API é thread-safe, utilizando locks para garantir consistência dos dados
