# Documentação da API REST e WebSocket - Backend

## Visão Geral

O backend expõe uma API REST para cadastro de produtos e WebSocket para comunicação em tempo real com o frontend. A API está disponível em `http://localhost:5000` por padrão.

**⚠️ IMPORTANTE:** A partir desta versão, a maioria dos endpoints requer **autenticação JWT**. Apenas `/api/ping` é público.

## Autenticação

O sistema utiliza **JWT (JSON Web Tokens)** para autenticação. Para acessar endpoints protegidos:

- Inclua o token no header `Authorization: Bearer <token>` em todas as requisições

### Fluxo de Autenticação

```bash
# 1. Registrar novo usuário
POST /api/auth/register

# 2. Fazer login e obter token
POST /api/auth/login

# 3. Usar token nas requisições
GET /api/produtos
Authorization: Bearer <seu-token-aqui>
```

---

## Endpoints de Autenticação

### 1. Registrar Usuário
**POST** `/api/auth/register`

Registra um novo usuário no sistema.

**Body (JSON):**
```json
{
  "username": "usuario123",
  "email": "usuario@example.com",
  "password": "senha123",
  "admin": false
}
```

**Campos:**
- `username` (obrigatório): Nome de usuário único
- `email` (obrigatório): Email único
- `password` (obrigatório): Senha (mínimo 6 caracteres)
- `admin` (opcional, padrão: false): Se o usuário é administrador

**Resposta (201):**
```json
{
  "mensagem": "Usuário registrado com sucesso",
  "usuario": {
    "usuario_id": 1,
    "username": "usuario123",
    "email": "usuario@example.com",
    "ativo": true,
    "admin": false,
    "criado_em": "2025-12-01T14:00:00",
    "ultimo_login": null
  }
}
```

**Erros:**
- `400`: Campos obrigatórios faltando ou senha muito curta
- `409`: Usuário ou email já existem
- `500`: Erro interno

---

### 2. Login
**POST** `/api/auth/login`

Autentica um usuário e retorna um token JWT.

**Body (JSON):**
```json
{
  "username": "usuario123",
  "password": "senha123"
}
```

**Resposta (200):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer",
  "usuario": {
    "usuario_id": 1,
    "username": "usuario123",
    "email": "usuario@example.com",
    "ativo": true,
    "admin": false,
    "criado_em": "2025-12-01T14:00:00",
    "ultimo_login": "2025-12-01T15:00:00"
  }
}
```

**Erros:**
- `400`: Credenciais não fornecidas
- `401`: Credenciais inválidas
- `403`: Usuário inativo

**Exemplo:**
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "usuario123",
    "password": "senha123"
  }'
```

---

### 3. Perfil do Usuário
**GET** `/api/auth/me`

Retorna informações do usuário autenticado.

**Headers:**
```
Authorization: Bearer <token>
```

**Resposta (200):**
```json
{
  "usuario_id": 1,
  "username": "usuario123",
  "email": "usuario@example.com",
  "ativo": true,
  "admin": false,
  "criado_em": "2025-12-01T14:00:00",
  "ultimo_login": "2025-12-01T15:00:00"
}
```

---

### 4. Listar Usuários (Admin)
**GET** `/api/auth/users`

Lista todos os usuários cadastrados. **Apenas administradores**.

**Headers:**
```
Authorization: Bearer <token>
```

**Resposta (200):**
```json
[
  {
    "usuario_id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "ativo": true,
    "admin": true,
    "criado_em": "2025-12-01T14:00:00",
    "ultimo_login": "2025-12-01T15:00:00"
  }
]
```

**Erros:**
- `401`: Token não fornecido ou inválido
- `403`: Acesso negado (apenas administradores)

---

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

**🔒 Requer autenticação**

**Headers:**
```
Authorization: Bearer <token>
```

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

**Validações:**
- Nome do produto é obrigatório
- Pesos devem ser maiores que zero
- `pesoMinimo` deve ser menor que `pesoMaximo`
- `pesoIdeal` deve estar entre `pesoMinimo` e `pesoMaximo`
- **Não permite dois produtos com o mesmo nome** (comparação case-insensitive)
- **Não permite dois produtos com o mesmo tópico MQTT**

**Erros:**
- `400`: Campos obrigatórios faltando ou valores inválidos
- `409`: Já existe um produto com o mesmo nome ou tópico
- `500`: Erro interno do servidor

**Exemplo de uso:**
```bash
# Primeiro, faça login para obter o token
TOKEN=$(curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "usuario123", "password": "senha123"}' \
  | jq -r '.access_token')

# Depois, use o token para cadastrar produto
curl -X POST http://localhost:5000/api/produtos \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "nome": "Leite",
    "pesoMinimo": 100,
    "pesoMaximo": 1000,
    "pesoIdeal": 500
  }'
```

**Exemplo de erro - produto duplicado:**
```bash
# Primeira tentativa - sucesso
curl -X POST http://localhost:5000/api/produtos \
  -H "Content-Type: application/json" \
  -d '{"nome": "Leite", "pesoMinimo": 100, "pesoMaximo": 1000}'

# Segunda tentativa - erro 409
curl -X POST http://localhost:5000/api/produtos \
  -H "Content-Type: application/json" \
  -d '{"nome": "Leite", "pesoMinimo": 50, "pesoMaximo": 500}'
# Resposta: {"erro": "Já existe um produto com o nome \"Leite\""}
```

**Exemplo de erro - tópico duplicado:**
```bash
# Primeira tentativa - sucesso
curl -X POST http://localhost:5000/api/produtos \
  -H "Content-Type: application/json" \
  -d '{"nome": "Leite", "topic": "estoque/custom/peso"}'

# Segunda tentativa - erro 409
curl -X POST http://localhost:5000/api/produtos \
  -H "Content-Type: application/json" \
  -d '{"nome": "Refrigerante", "topic": "estoque/custom/peso"}'
# Resposta: {"erro": "Já existe um produto usando o tópico \"estoque/custom/peso\""}
```

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

**🔒 Requer autenticação**

**Headers:**
```
Authorization: Bearer <token>
```

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

Simula a retirada manual de produtos (reduz o peso do estoque). **Centralizado no backend**: atualiza o sensor no publicador e publica mensagem MQTT.

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
  "mensagem": "Retirada executada com sucesso",
  "produto_id": 1,
  "produto_nome": "Leite",
  "peso_anterior": 750.50,
  "quantidade_retirada": 75.05,
  "peso_novo": 675.45,
  "sensor_atualizado": true,
  "mqtt_publicado": true
}
```

**Comportamento:**
1. Atualiza o peso diretamente no sensor do publicador (reflete na balança real)
2. Publica mensagem MQTT com a nova leitura
3. O sensor publicará automaticamente na próxima iteração

**Erros:**
- `404`: Produto não encontrado
- `400`: Valor inválido
- `500`: Erro ao publicar simulação MQTT

**Exemplo:**
```bash
# Retirada com quantidade específica
curl -X POST http://localhost:5000/api/produtos/1/retirada \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"quantidade": 50}'

# Retirada com quantidade aleatória
curl -X POST http://localhost:5000/api/produtos/1/retirada \
  -H "Authorization: Bearer $TOKEN"
```

---

### 6. Simular Reposição Manual
**POST** `/api/produtos/{produto_id}/reposicao`

Simula a reposição manual de produtos (aumenta o peso do estoque). **Centralizado no backend**: atualiza o sensor no publicador e publica mensagem MQTT.

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
  "mensagem": "Reposição executada com sucesso",
  "produto_id": 1,
  "produto_nome": "Leite",
  "peso_anterior": 150.50,
  "quantidade_adicionada": 25.0,
  "peso_novo": 175.50,
  "sensor_atualizado": true,
  "mqtt_publicado": true
}
```

**Nota:** O peso não ultrapassa o `pesoMaximo` cadastrado para o produto.

**Comportamento:**
1. Atualiza o peso diretamente no sensor do publicador (reflete na balança real)
2. Publica mensagem MQTT com a nova leitura
3. O sensor publicará automaticamente na próxima iteração

**Erros:**
- `404`: Produto não encontrado
- `400`: Valor inválido
- `500`: Erro ao publicar simulação MQTT

**Exemplo:**
```bash
# Reposição com quantidade específica
curl -X POST http://localhost:5000/api/produtos/1/reposicao \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"quantidade": 25}'

# Reposição com quantidade aleatória
curl -X POST http://localhost:5000/api/produtos/1/reposicao \
  -H "Authorization: Bearer $TOKEN"
```

---

## WebSocket

### Conexão

Conecte-se ao WebSocket em: `ws://localhost:5000`

**🔐 Autenticação Obrigatória:** O WebSocket requer autenticação JWT obrigatória via token no evento de conexão. Conexões sem token válido serão rejeitadas.

**Exemplo de conexão:**
```javascript
// 1. Primeiro, faça login para obter o token
const response = await fetch('http://localhost:5000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'usuario123',
    password: 'senha123'
  })
});

const { access_token } = await response.json();

// 2. Conecte ao WebSocket com o token
const socket = io('http://localhost:5000', {
  auth: {
    token: access_token
  }
});

socket.on('connect', () => {
  console.log('Conectado ao WebSocket');
});

socket.on('connect_error', (error) => {
  console.error('Erro ao conectar:', error.message);
  // Possíveis erros:
  // - Token não fornecido
  // - Token inválido ou expirado
  // - Usuário não encontrado ou inativo
});
```

### Eventos

#### 1. `connect` (Cliente → Servidor)
Evento automático quando o cliente se conecta com sucesso (após autenticação válida).

**Requisitos:**
- Token JWT válido deve ser fornecido no objeto `auth` da conexão
- O usuário associado ao token deve existir e estar ativo

**Resposta do servidor:**
O servidor envia automaticamente o evento `produtos_iniciais` com todos os produtos atuais.

**Erros de conexão:**
- Se o token não for fornecido, a conexão será rejeitada
- Se o token for inválido ou expirado, a conexão será rejeitada
- Se o usuário não existir ou estiver inativo, a conexão será rejeitada

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
- **Todas as requisições são centralizadas no backend**: retiradas/reposições atualizam o sensor no publicador E publicam MQTT
- As simulações automáticas continuam funcionando em paralelo com as simulações manuais
- O backend se comunica com o publicador via API REST para atualizar os sensores diretamente