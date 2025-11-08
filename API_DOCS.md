# Documentação da API REST e WebSocket - Backend

## Visão Geral

O backend expõe uma API REST para cadastro de produtos e WebSocket para comunicação em tempo real com o frontend. A API está disponível em `http://localhost:5000` por padrão.

## Endpoints REST

### 1. Health Check
**GET** `/api/ping`

Verifica se o servidor está ativo.

**Resposta:**
```json
{
  "status": "ok",
  "message": "pong"
}
```

---

### 2. Cadastrar Produto
**POST** `/api/produtos`

Cadastra um novo produto para simulação.

**Body (JSON):**
```json
{
  "nome": "Leite",
  "pesoMinimo": 100,
  "pesoMaximo": 1000,
  "pesoIdeal": 500,
  "topic": "estoque/produto1/peso"
}
```

**Campos:**
- `nome` (obrigatório): Nome do produto
- `pesoMinimo` (opcional, padrão: 100): Peso mínimo em KG (nível crítico)
- `pesoMaximo` (opcional, padrão: 1000): Peso máximo em KG
- `pesoIdeal` (opcional, padrão: pesoMinimo * 2): Peso ideal em KG (limite entre BAIXO e IDEAL)
- `topic` (opcional): Tópico MQTT personalizado. Se não informado, será gerado automaticamente

**Resposta (201):**
```json
{
  "produto_id": 1,
  "nome": "Leite",
  "pesoMinimo": 100,
  "pesoMaximo": 1000,
  "pesoIdeal": 500,
  "topic": "estoque/produto1/peso"
}
```

**Erros:**
- `400`: Campos obrigatórios faltando ou valores inválidos
- `500`: Erro interno do servidor

---

### 3. Listar Produtos Cadastrados
**GET** `/api/produtos`

Lista todos os produtos cadastrados.

**Resposta:**
```json
[
  {
    "produto_id": 1,
    "nome": "Leite",
    "pesoMinimo": 100,
    "pesoMaximo": 1000,
    "pesoIdeal": 500,
    "topic": "estoque/produto1/peso"
  }
]
```

---

### 4. Remover Produto
**DELETE** `/api/produtos/{produto_id}`

Remove um produto cadastrado.

**Parâmetros:**
- `produto_id` (int) - ID do produto

**Resposta (200):**
```json
{
  "mensagem": "Produto removido com sucesso"
}
```

**Erro 404:**
```json
{
  "erro": "Produto não encontrado"
}
```

---

### 5. Simular Retirada Manual
**POST** `/api/produtos/{produto_id}/retirada`

Simula a retirada manual de produtos (reduz o peso do estoque).

**Parâmetros:**
- `produto_id` (int) - ID do produto

**Body (JSON, opcional):**
```json
{
  "quantidade": 50.5
}
```

**Campos:**
- `quantidade` (opcional, em KG): Quantidade a ser retirada. Se não informado, usa valor aleatório (5-15% do peso atual)

**Resposta (200):**
```json
{
  "mensagem": "Retirada simulada com sucesso",
  "produto_id": 1,
  "produto_nome": "Leite",
  "peso_anterior": 750.50,
  "quantidade_retirada": 75.05,
  "peso_novo": 675.45
}
```

**Erros:**
- `404`: Produto não encontrado
- `400`: Valor inválido
- `500`: Erro ao publicar simulação MQTT

**Exemplo:**
```bash
# Retirada com quantidade específica
curl -X POST http://localhost:5000/api/produtos/1/retirada \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 50}'

# Retirada com quantidade aleatória
curl -X POST http://localhost:5000/api/produtos/1/retirada
```

---

### 6. Simular Reposição Manual
**POST** `/api/produtos/{produto_id}/reposicao`

Simula a reposição manual de produtos (aumenta o peso do estoque).

**Parâmetros:**
- `produto_id` (int) - ID do produto

**Body (JSON, opcional):**
```json
{
  "quantidade": 25.0
}
```

**Campos:**
- `quantidade` (opcional, em KG): Quantidade a ser adicionada. Se não informado, usa valor aleatório (1-5kg)

**Resposta (200):**
```json
{
  "mensagem": "Reposição simulada com sucesso",
  "produto_id": 1,
  "produto_nome": "Leite",
  "peso_anterior": 150.50,
  "quantidade_adicionada": 25.0,
  "peso_novo": 175.50
}
```

**Nota:** O peso não ultrapassa o `pesoMaximo` cadastrado para o produto.

**Erros:**
- `404`: Produto não encontrado
- `400`: Valor inválido
- `500`: Erro ao publicar simulação MQTT

**Exemplo:**
```bash
# Reposição com quantidade específica
curl -X POST http://localhost:5000/api/produtos/1/reposicao \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 25}'

# Reposição com quantidade aleatória
curl -X POST http://localhost:5000/api/produtos/1/reposicao
```

---

## WebSocket

### Conexão

Conecte-se ao WebSocket em: `ws://localhost:5000`

### Eventos

#### 1. `connect` (Cliente → Servidor)
Evento automático quando o cliente se conecta.

**Resposta do servidor:**
O servidor envia automaticamente o evento `produtos_iniciais` com todos os produtos atuais.

#### 2. `produtos_iniciais` (Servidor → Cliente)
Enviado quando um cliente se conecta, contendo todos os produtos cadastrados com dados atuais.

**Dados:**
```json
[
  {
    "Produto": "Leite",
    "nivelEstoque": 750.50,
    "pesoMinimo": 100,
    "pesoMaximo": 1000,
    "pesoAtual": 750.50,
    "ultimaAtualizacao": "2024-01-15 14:30:25"
  }
]
```

#### 3. `produto_atualizado` (Servidor → Cliente)
Enviado sempre que um produto recebe uma nova leitura de peso.

**Dados:**
```json
{
  "Produto": "Leite",
  "nivelEstoque": 750.50,
  "pesoMinimo": 100,
  "pesoMaximo": 1000,
  "pesoAtual": 750.50,
  "ultimaAtualizacao": "2024-01-15 14:30:25"
}
```

#### 4. `alerta` (Servidor → Cliente)
Enviado quando um produto atinge nível crítico.

**Dados:**
```json
{
  "produto_id": 1,
  "produto_nome": "Leite",
  "peso_atual": 80.50,
  "peso_critico": 100,
  "tipo": "REPOSICAO_URGENTE",
  "mensagem": "⚠️ PESO CRÍTICO! Reposição necessária para Leite",
  "timestamp": "2024-01-15 14:35:10"
}
```

---

## Formato de Dados WebSocket

### Produto Atualizado

```json
{
  "Produto": "NomeProduto",
  "nivelEstoque": 750.50,
  "pesoMinimo": 100,
  "pesoMaximo": 1000,
  "pesoAtual": 750.50,
  "ultimaAtualizacao": "2024-01-15 14:30:25"
}
```

**Campos:**
- `Produto`: Nome do produto
- `nivelEstoque`: Peso atual em KG (igual a pesoAtual)
- `pesoMinimo`: Peso mínimo em KG (nível crítico)
- `pesoMaximo`: Peso máximo em KG
- `pesoAtual`: Peso atual em KG
- `ultimaAtualizacao`: Timestamp da última leitura (formato: "YYYY-MM-DD HH:MM:SS")

---

## Estados de Estoque

Os produtos podem estar em três estados, calculados automaticamente:

1. **CRITICO**: Peso atual ≤ pesoMinimo
2. **BAIXO**: Peso atual > pesoMinimo e ≤ pesoIdeal
3. **IDEAL**: Peso atual > pesoIdeal

---

## Exemplos de Uso

### JavaScript (WebSocket)

```javascript
const socket = io('http://localhost:5000');

// Conectar
socket.on('connect', () => {
  console.log('Conectado ao WebSocket');
});

// Receber produtos iniciais
socket.on('produtos_iniciais', (produtos) => {
  console.log('Produtos iniciais:', produtos);
});

// Receber atualização de produto
socket.on('produto_atualizado', (produto) => {
  console.log('Produto atualizado:', produto);
});

// Receber alerta
socket.on('alerta', (alerta) => {
  console.log('Alerta:', alerta);
});
```

### Python (requests - Cadastrar Produto)

```python
import requests

# Cadastrar produto
produto = {
    "nome": "Leite",
    "pesoMinimo": 100,
    "pesoMaximo": 1000,
    "pesoIdeal": 500
}

response = requests.post('http://localhost:5000/api/produtos', json=produto)
print(response.json())
```

### cURL

```bash
# Health check
curl http://localhost:5000/api/ping

# Cadastrar produto
curl -X POST http://localhost:5000/api/produtos \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Leite",
    "pesoMinimo": 100,
    "pesoMaximo": 1000,
    "pesoIdeal": 500
  }'

# Listar produtos
curl http://localhost:5000/api/produtos

# Remover produto
curl -X DELETE http://localhost:5000/api/produtos/1

# Simular retirada (quantidade específica)
curl -X POST http://localhost:5000/api/produtos/1/retirada \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 50}'

# Simular retirada (quantidade aleatória)
curl -X POST http://localhost:5000/api/produtos/1/retirada

# Simular reposição (quantidade específica)
curl -X POST http://localhost:5000/api/produtos/1/reposicao \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 25}'

# Simular reposição (quantidade aleatória)
curl -X POST http://localhost:5000/api/produtos/1/reposicao
```

---

## CORS

A API possui CORS habilitado, permitindo requisições de qualquer origem.

---

## Notas

- Todos os endpoints REST retornam dados em formato JSON
- Os pesos são sempre em **KG** (quilogramas)
- Os timestamps estão no formato `YYYY-MM-DD HH:MM:SS`
- Cada produto possui um sensor único (1 sensor = 1 produto)
- Os alertas são enviados via WebSocket quando o peso atinge nível crítico
- O tópico MQTT é gerado automaticamente se não informado
- O publicador busca produtos cadastrados via API automaticamente
- As simulações manuais de retirada/reposição publicam mensagens MQTT que são processadas normalmente pelo backend
- As simulações automáticas continuam funcionando em paralelo com as simulações manuais