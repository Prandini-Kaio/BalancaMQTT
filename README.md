# Sistema de Monitoramento de Estoque por Peso - MQTT

Sistema completo de monitoramento de estoque usando sensores de peso que se comunicam via protocolo MQTT. O sistema simula produtos inteligentes com sensores que medem continuamente o peso dos produtos e emitem alertas quando o estoque está baixo.

## 📋 Funcionalidades

- ✅ Simulação de múltiplos produtos com sensores de peso (1 sensor = 1 produto)
- ✅ Publicação contínua de leituras via MQTT
- ✅ Detecção automática de níveis críticos de estoque
- ✅ Alertas de reposição em tempo real
- ✅ Armazenamento de dados em arquivo CSV
- ✅ API REST para acesso aos dados pelo frontend
- ✅ Métricas gerais do sistema (total de produtos, estados, etc.)
- ✅ Estados de estoque: CRÍTICO, BAIXO, IDEAL

## 🛠️ Tecnologias

- **Python 3.7+**
- **Paho-MQTT** - Biblioteca cliente MQTT
- **Flask** - Framework web para API REST
- **Flask-CORS** - CORS para API
- **CSV** - Armazenamento de dados
- **JSON** - Formato de mensagens

## 📦 Instalação

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Instalar e configurar um broker MQTT

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

### 1. Iniciar o Servidor Backend

Abra um terminal e execute:

```bash
python src/servidor_assinante.py
```

O servidor irá:
- Conectar ao broker MQTT
- Inscrever-se nos tópicos de estoque
- Exibir leituras recebidas no console
- Salvar dados no arquivo `dados.csv`
- Iniciar API REST em `http://localhost:5000`

### 2. Iniciar os Sensores (Publicador)

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

Além da simulação automática realizada pelos sensores, é possível simular retiradas e reposições manualmente através de duas APIs REST:

### Via Backend (publica mensagens MQTT)

O backend pode simular retiradas/reposições que publicam mensagens MQTT:

```bash
# Retirada via backend
curl -X POST http://localhost:5000/api/produtos/1/retirada \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 50}'

# Reposição via backend
curl -X POST http://localhost:5000/api/produtos/1/reposicao \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 25}'
```

### Via Publicador (modifica peso diretamente no sensor)

O publicador expõe uma API REST na porta 5001 para controle direto dos sensores:

```bash
# Listar sensores ativos
curl http://localhost:5001/api/sensores

# Status de um sensor específico
curl http://localhost:5001/api/sensores/1

# Retirar peso diretamente do sensor
curl -X POST http://localhost:5001/api/sensores/1/retirada \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 30}'

# Repor peso diretamente no sensor
curl -X POST http://localhost:5001/api/sensores/1/reposicao \
  -H "Content-Type: application/json" \
  -d '{"quantidade": 20}'
```

**Diferenças:**
- **Backend (`/api/produtos/{id}/retirada`)**: Publica mensagem MQTT que simula uma leitura de sensor
- **Publicador (`/api/sensores/{id}/retirada`)**: Modifica o peso diretamente no sensor, que publicará a nova leitura na próxima iteração

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
│   └── servidor_assinante.py     # Servidor backend (assinante + API)
├── requirements.txt              # Dependências Python
├── README.md                     # Este arquivo
├── API_DOCS.md                   # Documentação da API REST do backend
├── PUBLICADOR_API_DOCS.md        # Documentação da API REST do publicador
└── dados.csv                     # Dados salvos (gerado automaticamente)
```

## 📄 Licença

Este projeto foi desenvolvido para fins educacionais.

## 👨‍💻 Autor

Sistema de Monitoramento de Estoque por Peso - MQTT
Desenvolvido para projeto acadêmico
