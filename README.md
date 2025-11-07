# Sistema de Monitoramento de Estoque por Peso - MQTT

Sistema completo de monitoramento de estoque usando sensores de peso que se comunicam via protocolo MQTT. O sistema simula prateleiras inteligentes com sensores que medem continuamente o peso dos produtos e emitem alertas quando o estoque está baixo.

## 📋 Funcionalidades

- ✅ Simulação de múltiplas prateleiras com sensores de peso
- ✅ Publicação contínua de leituras via MQTT
- ✅ Detecção automática de níveis críticos de estoque
- ✅ Alertas de reposição em tempo real
- ✅ Armazenamento de dados em arquivo CSV
- ✅ Interface de console para monitoramento
- ✅ Configuração flexível de prateleiras e sensores

## 🛠️ Tecnologias

- **Python 3.7+**
- **Paho-MQTT** - Biblioteca cliente MQTT
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

### 1. Iniciar o Servidor Coletor (Assinante)

Abra um terminal e execute:

```bash
python servidor_assinante.py
```

O servidor irá:
- Conectar ao broker MQTT
- Inscrever-se nos tópicos de estoque
- Exibir leituras recebidas no console
- Salvar dados no arquivo `dados.csv`

### 2. Iniciar os Sensores (Publicador)

Abra outro terminal e execute:

```bash
python balancas_publicador.py
```

**Configuração padrão:**
- Prateleira 1: 1 sensor
- Prateleira 2: 2 sensores
- Prateleira 3: 1 sensor

**Personalizar configuração:**
```bash
python balancas_publicador.py --prateleiras "1:1,2:3,3:2,4:1"
```

Isso criará:
- Prateleira 1 com 1 sensor
- Prateleira 2 com 3 sensores
- Prateleira 3 com 2 sensores
- Prateleira 4 com 1 sensor

### 3. Opções de Linha de Comando

#### Publicador (`balancas_publicador.py`)

```bash
python balancas_publicador.py --help

Opções:
  --broker HOST        Endereço do broker MQTT (padrão: localhost)
  --port PORT          Porta do broker MQTT (padrão: 1883)
  --prateleiras CONFIG Configuração no formato "id:num_sensores,id:num_sensores"
```

**Exemplos:**
```bash
# Usar broker remoto
python balancas_publicador.py --broker test.mosquitto.org --port 1883

# Configuração personalizada
python balancas_publicador.py --prateleiras "1:2,2:1,3:3"
```

#### Servidor (`servidor_assinante.py`)

```bash
python servidor_assinante.py --help

Opções:
  --broker HOST        Endereço do broker MQTT (padrão: localhost)
  --port PORT          Porta do broker MQTT (padrão: 1883)
  --csv ARQUIVO        Arquivo CSV para salvar dados (padrão: dados.csv)
```

**Exemplos:**
```bash
# Usar broker remoto
python servidor_assinante.py --broker test.mosquitto.org --port 1883

# Arquivo CSV personalizado
python servidor_assinante.py --csv estoque_2024.csv
```

## 📊 Estrutura de Dados

### Mensagens de Peso

**Tópico:** `estoque/prateleira{id}/sensor{id}/peso`

```json
{
  "prateleira_id": 1,
  "sensor_id": 1,
  "peso_gramas": 4500.50,
  "peso_inicial": 7500.00,
  "percentual_restante": 60.0,
  "timestamp": "2024-01-15 14:30:25"
}
```

### Mensagens de Alerta

**Tópico:** `estoque/prateleira{id}/sensor{id}/alerta`

```json
{
  "prateleira_id": 1,
  "sensor_id": 1,
  "peso_atual": 1200.00,
  "peso_critico": 1500.00,
  "tipo": "REPOSICAO_URGENTE",
  "mensagem": "⚠️ PESO CRÍTICO! Reposição necessária na Prateleira 1, Sensor 1",
  "timestamp": "2024-01-15 14:35:10"
}
```

### Arquivo CSV

O arquivo `dados.csv` contém:
- `timestamp_recebimento`: Data/hora da recepção
- `tipo`: PESO ou ALERTA
- `prateleira_id`: ID da prateleira
- `sensor_id`: ID do sensor
- `peso_gramas`: Peso atual em gramas
- `peso_inicial`: Peso inicial em gramas
- `percentual_restante`: Percentual restante
- `peso_critico`: Peso crítico (apenas para alertas)
- `tipo_alerta`: Tipo de alerta (apenas para alertas)
- `mensagem`: Mensagem do alerta (apenas para alertas)

## 📸 Exemplo de Saída

### Console do Publicador

```
======================================================================
SISTEMA DE SIMULAÇÃO DE SENSORES DE PESO - PUBLICADOR MQTT
======================================================================
Broker: localhost:1883
Configuração: {1: 1, 2: 2, 3: 1}
======================================================================
[CONECTADO] Broker MQTT: localhost:1883

[INFO] Iniciando 4 sensor(es)...
======================================================================
[INICIADO] Sensor 1 da Prateleira 1 (Peso inicial: 6823.45g, Crítico: 1364.69g)
[INICIADO] Sensor 1 da Prateleira 2 (Peso inicial: 7234.12g, Crítico: 1446.82g)
[INICIADO] Sensor 2 da Prateleira 2 (Peso inicial: 5891.23g, Crítico: 1178.25g)
[INICIADO] Sensor 1 da Prateleira 3 (Peso inicial: 8123.67g, Crítico: 1624.73g)

[PUBLICADOR] Prateleira 1 - Sensor 1: 6823.45g (100.0% restante)
[PUBLICADOR] Prateleira 2 - Sensor 1: 7234.12g (100.0% restante)
[PUBLICADOR] Prateleira 2 - Sensor 2: 5891.23g (100.0% restante)
[PUBLICADOR] Prateleira 3 - Sensor 1: 8123.67g (100.0% restante)
```

### Console do Servidor

```
======================================================================
SERVIDOR COLETOR - ASSINANTE MQTT
======================================================================
Broker: localhost:1883
Tópico: estoque/+
Arquivo CSV: dados.csv
======================================================================
[CONECTADO] Broker MQTT: localhost:1883
[INSCRITO] Tópico: estoque/+
[INFO] Inscrição confirmada (QoS: 1)
======================================================================
[AGUARDANDO] Dados dos sensores...
======================================================================

[📊 LEITURA #1]
   Prateleira: 1 | Sensor: 1
   Peso: 6823.45g | Percentual restante: 100.0%
   Timestamp: 2024-01-15 14:30:25

[📊 LEITURA #2]
   Prateleira: 2 | Sensor: 1
   Peso: 7234.12g | Percentual restante: 100.0%
   Timestamp: 2024-01-15 14:30:25

======================================================================
⚠️  [ALERTA #1] ⚠️
======================================================================
   ⚠️ PESO CRÍTICO! Reposição necessária na Prateleira 2, Sensor 1
   Prateleira: 2 | Sensor: 1
   Peso atual: 1200.50g
   Timestamp: 2024-01-15 14:35:10
======================================================================
```

## ⚙️ Configurações

### Parâmetros Ajustáveis (no código)

No arquivo `balancas_publicador.py`:

```python
PESO_INICIAL_MIN = 5000      # Peso mínimo inicial (gramas)
PESO_INICIAL_MAX = 10000     # Peso máximo inicial (gramas)
PESO_CRITICO_PERCENTUAL = 0.2  # 20% do peso inicial = nível crítico
INTERVALO_MEDICAO = 3        # Intervalo entre medições (segundos)
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

## 📝 Estrutura do Projeto

```
BalancaMQTT/
│
├── balancas_publicador.py    # Simula sensores de peso (publicador)
├── servidor_assinante.py     # Servidor coletor (assinante)
├── requirements.txt          # Dependências Python
├── README.md                 # Este arquivo
└── dados.csv                 # Dados salvos (gerado automaticamente)
```

## 👨‍💻 Autores

Sistema de Monitoramento de Estoque por Peso MQTT
Desenvolvido para projeto acadêmico de IOT da Pontificia Universidade Catolica de Minas Gerais.
- https://github.com/prandini-kaio
- https://github.com/RafaZNavarro
- https://github.com/Nogs0
- https://github.com/dudu-passoni
