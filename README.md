# Sistema de Monitoramento de Estoque por Peso - MQTT

Sistema completo de monitoramento de estoque usando sensores de peso que se comunicam via protocolo MQTT. O sistema simula produtos inteligentes com sensores que medem continuamente o peso dos produtos e emitem alertas quando o estoque está baixo.

## 📋 Funcionalidades

- ✅ Simulação de múltiplos produtos com sensores de peso (1 sensor = 1 produto)
- ✅ Publicação contínua de leituras via MQTT
- ✅ Detecção automática de níveis críticos de estoque
- ✅ Alertas de reposição em tempo real
- ✅ **Persistência de dados em banco de dados PostgreSQL**
- ✅ Armazenamento de backup em arquivo CSV
- ✅ API REST para acesso aos dados pelo frontend
- ✅ WebSocket para atualizações em tempo real
- ✅ Métricas gerais do sistema (total de produtos, estados, etc.)
- ✅ Estados de estoque: CRÍTICO, BAIXO, IDEAL
- ✅ **Dockerização completa do sistema**

## 🛠️ Tecnologias

- **Python 3.11+**
- **Paho-MQTT** - Biblioteca cliente MQTT
- **Flask** - Framework web para API REST
- **Flask-SocketIO** - WebSocket para comunicação em tempo real
- **Flask-CORS** - CORS para API
- **SQLAlchemy** - ORM para banco de dados
- **PostgreSQL** - Banco de dados relacional
- **Docker & Docker Compose** - Containerização
- **CSV** - Backup de dados
- **JSON** - Formato de mensagens

## 📦 Instalação

### Opção 1: Docker 🐳

A forma mais fácil de executar o sistema é usando Docker Compose:

```bash
# Clonar ou baixar o projeto
cd BalancaMQTT

# Iniciar todos os serviços (PostgreSQL + Backend + Publicador)
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar os serviços
docker-compose down
```

**Serviços disponíveis:**
- **Backend**: http://localhost:5000
- **Publicador**: http://localhost:5001
- **PostgreSQL**: localhost:5432

**Variáveis de ambiente** podem ser configuradas no arquivo `.env` ou no `docker-compose.yml`.

### Opção 2: Instalação Manual

#### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

#### 2. Configurar banco de dados PostgreSQL

Instale e configure o PostgreSQL, depois crie o banco:

```bash
# Criar banco de dados
createdb balancas_db

# Ou via psql
psql -U postgres -c "CREATE DATABASE balancas_db;"
```

Configure a variável de ambiente `DATABASE_URL`:

```bash
export DATABASE_URL="postgresql://usuario:senha@localhost:5432/balancas_db"
```

Ou crie um arquivo `.env`:

```bash
DATABASE_URL=postgresql://usuario:senha@localhost:5432/balancas_db
```

#### 3. Inicializar banco de dados

```bash
python init_db.py
```

#### 3. Instalar e configurar um broker MQTT

#### Opção A: Mosquitto (Recomendado)

**Windows:**
1. Baixe o Mosquitto em: https://mosquitto.org/download/
2. Instale e inicie o serviço Mosquitto

**Linux:**
```bash
sudo apt-get install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

**macOS:**
```bash
brew install mosquitto
brew services start mosquitto
```

#### Opção B: Broker MQTT online (para testes)

Você pode usar um broker público como:
- `test.mosquitto.org` (porta 1883)
- `broker.hivemq.com` (porta 1883)

## 🚀 Como Usar

### Com Docker

```bash
# Iniciar tudo
docker-compose up -d

# Ver logs do backend
docker-compose logs -f backend

# Ver logs do publicador
docker-compose logs -f publicador

# Ver logs do banco
docker-compose logs -f postgres
```

### Manualmente

#### 1. Iniciar o Servidor Backend

Abra um terminal e execute:

```bash
python src/servidor_assinante.py
```

O servidor irá:
- Conectar ao banco de dados PostgreSQL
- Criar tabelas automaticamente (se não existirem)
- Conectar ao broker MQTT
- Inscrever-se nos tópicos de estoque
- Exibir leituras recebidas no console
- Salvar dados no banco de dados e arquivo `dados.csv` (backup)
- Iniciar API REST em `http://localhost:5000`
- Iniciar WebSocket em `ws://localhost:5000`

#### 2. Iniciar os Sensores (Publicador)

Abra outro terminal e execute:

```bash
python src/balancas_publicador.py
```

**Comportamento:**
- O publicador busca produtos cadastrados via API do backend
- Se não houver produtos cadastrados, o publicador aguarda e verifica periodicamente (a cada 10 segundos)
- Novos produtos cadastrados são automaticamente detectados e seus sensores são iniciados
- O publicador expõe uma API REST na porta 5001 para controle direto dos sensores

### 3. Opções de Linha de Comando

#### Publicador (`balancas_publicador.py`)

```bash
python src/balancas_publicador.py --help

Opções:
  --broker HOST              Endereço do broker MQTT (padrão: test.mosquitto.org)
  --port PORT                Porta do broker MQTT (padrão: 1883)
  --api-url URL              URL da API backend (padrão: http://localhost:5000)
  --api-port-publicador PORT Porta da API REST do publicador (padrão: 5001)
```

**Exemplos:**
```bash
# Usar broker remoto
python src/balancas_publicador.py --broker test.mosquitto.org --port 1883

# API do publicador em porta diferente
python src/balancas_publicador.py --api-port-publicador 5002
```

#### Servidor Backend (`servidor_assinante.py`)

```bash
python src/servidor_assinante.py --help

Opções:
  --broker HOST        Endereço do broker MQTT (padrão: test.mosquitto.org)
  --port PORT          Porta do broker MQTT (padrão: 1883)
  --csv ARQUIVO        Arquivo CSV para salvar dados (padrão: dados.csv)
  --api-host HOST      Host da API REST (padrão: 0.0.0.0)
  --api-port PORT      Porta da API REST (padrão: 5000)
```

**Exemplos:**
```bash
# Usar broker remoto
python src/servidor_assinante.py --broker test.mosquitto.org --port 1883

# Arquivo CSV personalizado
python src/servidor_assinante.py --csv estoque_2024.csv

# Porta da API personalizada
python src/servidor_assinante.py --api-port 8000
```

## 🎮 Simulação Manual

Além da simulação automática realizada pelos sensores, é possível simular retiradas e reposições manualmente através do backend. **Todas as requisições são centralizadas no backend**, que:
1. Atualiza o peso diretamente no sensor do publicador (reflete na balança real)
2. Publica mensagem MQTT com a nova leitura

### Via Backend (centralizado)

```bash
# Retirada via backend (atualiza sensor + MQTT)
curl -X POST http://localhost:5000/api/produtos/1/retirada \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 50}'

# Reposição via backend (atualiza sensor + MQTT)
curl -X POST http://localhost:5000/api/produtos/1/reposicao \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 25}'
```

### API do Publicador (avançado)

O publicador também expõe uma API REST na porta 5001 para acesso direto aos sensores (uso avançado):

```bash
# Listar sensores ativos
curl http://localhost:5001/api/sensores

# Status de um sensor específico
curl http://localhost:5001/api/sensores/1
```

**Nota:** Para operações de retirada/reposição, use sempre o backend (`/api/produtos/{id}/retirada` ou `/reposicao`), que garante que tanto o sensor quanto o MQTT sejam atualizados corretamente.

## 📊 Estrutura de Dados

### Mensagens de Peso

**Tópico:** `estoque/produto{id}/peso`

```json
{
  "produto_id": 1,
  "produto_nome": "Leite",
  "peso_gramas": 750500.50,
  "peso_inicial": 1000000.00,
  "percentual_restante": 75.05,
  "timestamp": "2024-01-15 14:30:25"
}
```

### Mensagens de Alerta

**Tópico:** `estoque/produto{id}/alerta`

```json
{
  "produto_id": 1,
  "produto_nome": "Leite",
  "peso_atual": 150000.00,
  "peso_critico": 200000.00,
  "tipo": "REPOSICAO_URGENTE",
  "mensagem": "⚠️ PESO CRÍTICO! Reposição necessária para Leite",
  "timestamp": "2024-01-15 14:35:10"
}
```

### Arquivo CSV

O arquivo `dados.csv` contém:
- `timestamp_recebimento`: Data/hora da recepção
- `tipo`: PESO ou ALERTA
- `produto_id`: ID do produto
- `produto_nome`: Nome do produto
- `peso_gramas`: Peso atual em gramas
- `peso_inicial`: Peso inicial em gramas
- `percentual_restante`: Percentual restante
- `peso_critico`: Peso crítico (apenas para alertas)
- `tipo_alerta`: Tipo de alerta (apenas para alertas)
- `mensagem`: Mensagem do alerta (apenas para alertas)

## 🌐 API REST

O sistema expõe duas APIs REST:

1. **Backend** (`http://localhost:5000`): [Documentação completa](API_DOCS.md)
2. **Publicador** (`http://localhost:5001`): [Documentação completa](PUBLICADOR_API_DOCS.md)

### Funcionalidades da API

**Backend (porta 5000):**
- ✅ Cadastro de produtos
- ✅ Listagem de produtos cadastrados
- ✅ Remoção de produtos
- ✅ Simulação manual de retirada/reposição (publica MQTT)
- ✅ WebSocket para atualizações em tempo real

**Publicador (porta 5001):**
- ✅ Listagem de sensores ativos
- ✅ Status de sensores individuais
- ✅ Retirada/reposição de peso diretamente nos sensores
- ✅ Detecção automática de novos produtos cadastrados

### Endpoints Principais

- `GET /api/ping` - Status do servidor
- `POST /api/produtos` - Cadastrar novo produto
- `GET /api/produtos` - Lista todos os produtos cadastrados
- `DELETE /api/produtos/{id}` - Remover produto
- `POST /api/produtos/{id}/retirada` - Simular retirada manual
- `POST /api/produtos/{id}/reposicao` - Simular reposição manual

### Exemplo de Resposta da API

```json
{
  "produto_id": 1,
  "nomeProduto": "Leite",
  "nivelEstoque": 750.50,
  "pesoMinimo": 200.00,
  "pesoMaximo": 1000.00,
  "pesoAtual": 750.50,
  "ultimaAtualizacao": "2024-01-15 14:30:25",
  "estado": "IDEAL",
  "percentual": 75.05
}
```

## ⚙️ Configurações

### Parâmetros Ajustáveis (no código)

No arquivo `src/balancas_publicador.py`:

```python
PESO_INICIAL_MIN = 100000      # Peso mínimo inicial (gramas) - 100kg
PESO_INICIAL_MAX = 1000000     # Peso máximo inicial (gramas) - 1000kg
INTERVALO_MEDICAO = 3          # Intervalo entre medições (segundos)
```

### Simulação

O sistema possui dois modos de simulação:

1. **Automática**: Os sensores simulam retiradas e reposições aleatoriamente
2. **Manual**: Endpoints REST permitem simular retiradas e reposições de forma controlada

Ambas as formas funcionam simultaneamente e publicam mensagens MQTT que são processadas normalmente pelo backend.

## 📸 Exemplo de Saída

### Console do Publicador

```
======================================================================
SISTEMA DE SIMULAÇÃO DE SENSORES DE PESO - PUBLICADOR MQTT
======================================================================
Broker: test.mosquitto.org:1883
Configuração: {1: 'Leite', 2: 'Refrigerante', 3: 'Pão'}
======================================================================
[CONECTADO] Broker MQTT: test.mosquitto.org:1883

[INFO] Iniciando 3 produto(s)...
======================================================================
[INICIADO] Leite - Produto ID 1 (Peso inicial: 750.00kg, Crítico: 150.00kg)
[INICIADO] Refrigerante - Produto ID 2 (Peso inicial: 850.00kg, Crítico: 170.00kg)
[INICIADO] Pão - Produto ID 3 (Peso inicial: 600.00kg, Crítico: 120.00kg)

[PUBLICADOR] Leite: 750.00kg (100.0% restante)
[PUBLICADOR] Refrigerante: 850.00kg (100.0% restante)
[PUBLICADOR] Pão: 600.00kg (100.0% restante)
```

### Console do Servidor Backend

```
======================================================================
SERVIDOR BACKEND - MQTT + API REST
======================================================================
Broker MQTT: test.mosquitto.org:1883
Tópico: estoque/#
API REST: http://0.0.0.0:5000
Arquivo CSV: dados.csv
======================================================================
[API] Servidor REST iniciado em http://0.0.0.0:5000
[CONECTADO] Broker MQTT: test.mosquitto.org:1883
[INSCRITO] Tópico: estoque/#
[INFO] Inscrição confirmada (QoS: 1)
======================================================================
[AGUARDANDO] Dados dos sensores...
======================================================================

[📊 LEITURA #1]
   Leite: 750.50kg (75.1% restante) - Estado: IDEAL

[📊 LEITURA #2]
   Refrigerante: 150.20kg (10.0% restante) - Estado: CRITICO

======================================================================
⚠️  [ALERTA #1] ⚠️
======================================================================
   ⚠️ PESO CRÍTICO! Reposição necessária para Refrigerante
   Produto: Refrigerante
   Peso atual: 150.20kg
   Timestamp: 2024-01-15 14:35:10
======================================================================
```

## 🔧 Troubleshooting

### Erro: "Não foi possível conectar ao broker"

**Solução:**
1. Verifique se o broker MQTT está rodando
2. Teste a conexão: `mosquitto_sub -h localhost -t test`
3. Use um broker público para testes: `--broker test.mosquitto.org`

### Erro: "ModuleNotFoundError: No module named 'paho'"

**Solução:**
```bash
pip install -r requirements.txt
```

### Dados não aparecem no servidor

**Solução:**
1. Verifique se ambos os scripts estão conectados ao mesmo broker
2. Verifique se o servidor está inscrito no tópico correto
3. Verifique logs de erro no console

### API não responde

**Solução:**
1. Verifique se o servidor backend está rodando
2. Verifique a porta da API (padrão: 5000)
3. Teste o endpoint: `curl http://localhost:5000/api/ping`

## 📝 Estrutura do Projeto

```
BalancaMQTT/
│
├── src/
│   ├── balancas_publicador.py    # Simula sensores de peso (publicador)
│   ├── servidor_assinante.py     # Servidor backend (assinante + API)
│   ├── models.py                 # Modelos SQLAlchemy (Produto, Leitura, Alerta)
│   └── config.py                 # Configurações do sistema
├── requirements.txt              # Dependências Python
├── Dockerfile.backend            # Dockerfile para o backend
├── Dockerfile.publicador         # Dockerfile para o publicador
├── docker-compose.yml            # Orquestração Docker Compose
├── init_db.py                    # Script de inicialização do banco
├── .dockerignore                 # Arquivos ignorados no Docker
├── README.md                     # Este arquivo
├── API_DOCS.md                   # Documentação da API REST do backend
└── dados.csv                     # Backup CSV (gerado automaticamente)
```

## 🗄️ Banco de Dados

O sistema utiliza PostgreSQL para persistência de dados com as seguintes tabelas:

- **`produtos`**: Cadastro de produtos (nome, pesos, tópico MQTT)
- **`leituras`**: Histórico de todas as leituras de peso recebidas
- **`alertas`**: Histórico de alertas de reposição

O banco é inicializado automaticamente na primeira execução. Para reinicializar:

```bash
# Com Docker
docker-compose down -v  # Remove volumes
docker-compose up -d    # Recria tudo

# Manualmente
python init_db.py
```

Agradecemos às seguintes pessoas que contribuíram para este projeto:

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/prandini-kaio/" title="Perfil de Kaio Prandini no GitHub">
        <img src="https://avatars.githubusercontent.com/u/73852163?s=400&u=ca4d7ff329ee88f529ea386b8b42a95918de08bb&v=4" width="100px;" alt="Foto de Kaio Prandini no GitHub"/><br>
        <sub>
          <b>Kaio Prandini</b>
        </sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/rafaznavarro/" title="Perfil de Rafael Navarro no GitHub">
        <img src="https://avatars.githubusercontent.com/u/118142650?v=4" width="100px;" alt="Foto de Rafael Navarro no GitHub"/><br>
        <sub>
          <b>Rafael Navarro</b>
        </sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/Nogs0/" title="Perfil de João Nogueira no GitHub">
        <img src="https://avatars.githubusercontent.com/u/108362664?v=4" width="100px;" alt="Foto de João Nogueira no GitHub"/><br>
        <sub>
          <b>João Nogueira</b>
        </sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/dudu-passoni/" title="Perfil de Dudu Passoni no GitHub">
        <img src="https://avatars.githubusercontent.com/u/115907714?v=4" width="100px;" alt="Foto de João Nogueira no GitHub"/><br>
        <sub>
          <b>Luis Eduardo Passoni</b>
        </sub>
      </a>
    </td>
    <td align="center">
      <a href="#" title="defina o título do link">
        <img src="https://s2.glbimg.com/FUcw2usZfSTL6yCCGj3L3v3SpJ8=/smart/e.glbimg.com/og/ed/f/original/2019/04/25/zuckerberg_podcast.jpg" width="100px;" alt="Foto do Mark Zuckerberg"/><br>
        <sub>
          <b>Mark Zuckerberg</b>
        </sub>
      </a>
    </td>
    <td align="center">
      <a href="#" title="defina o título do link">
        <img src="https://miro.medium.com/max/360/0*1SkS3mSorArvY9kS.jpg" width="100px;" alt="Foto do Steve Jobs"/><br>
        <sub>
          <b>Steve Jobs</b>
        </sub>
      </a>
    </td>
  </tr>
</table>