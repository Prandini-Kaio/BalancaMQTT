import paho.mqtt.client as mqtt
import json
import csv
import os
import time
import random
import requests
from datetime import datetime
import argparse
from threading import Thread, Lock
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Config padrao
BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883
TOPIC_BASE = "estoque"
TOPIC_SUBSCRIBE = f"{TOPIC_BASE}/#"
ARQUIVO_CSV = "dados.csv"
API_HOST = "0.0.0.0"
API_PORT = 5000
PUBLICADOR_API_URL = "http://localhost:5001"


"""
Servidor Backend - Coletor MQTT + WebSocket + API REST
Recebe dados MQTT de sensores de produtos e expõe WebSocket para frontend
"""

class ServidorBackend:
    """Classe que gerencia o servidor coletor de dados MQTT"""
    
    def __init__(self, broker_host, broker_port, arquivo_csv, api_host, api_port, publicador_api_url):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.arquivo_csv = arquivo_csv
        self.api_host = api_host
        self.api_port = api_port
        self.publicador_api_url = publicador_api_url
        
        # Cliente MQTT (assinante)
        self.client = mqtt.Client(client_id="servidor_coletor")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        
        # Cliente MQTT para publicação (simulação manual)
        self.client_publisher = mqtt.Client(client_id="servidor_coletor_publisher")
        self.client_publisher_connected = False
        
        # Armazenamento em memória
        self.lock = Lock()
        self.leituras_recebidas = 0
        self.alertas_recebidos = 0

        self.produtos_cadastrados = {}
        self.produtos_dados = {}
        self.next_produto_id = 1
        
        # Flask + SocketIO
        self.app = Flask(__name__)
        CORS(self.app)
        self.socketio = SocketIO(
            self.app, 
            cors_allowed_origins="*", 
            async_mode='threading',
            ping_timeout=60,
            ping_interval=25
        )
        self._configurar_rotas()
        self._configurar_websocket()
        
        self.inicializar_csv()
    
    def inicializar_csv(self):
        """Cria o arquivo CSV com cabeçalho se não existir"""
        if not os.path.exists(self.arquivo_csv):
            with open(self.arquivo_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp_recebimento',
                    'tipo',
                    'produto_id',
                    'produto_nome',
                    'peso_gramas',
                    'peso_inicial',
                    'percentual_restante',
                    'peso_critico',
                    'tipo_alerta',
                    'mensagem'
                ])
            print(f"[INFO] Arquivo CSV criado: {self.arquivo_csv}")
    
    def salvar_csv(self, dados, tipo='peso'):
        """Salva dados no arquivo CSV"""
        try:
            with open(self.arquivo_csv, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                timestamp_recebimento = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if tipo == 'peso':
                    writer.writerow([
                        timestamp_recebimento,
                        'PESO',
                        dados.get('produto_id', ''),
                        dados.get('produto_nome', ''),
                        dados.get('peso_gramas', ''),
                        dados.get('peso_inicial', ''),
                        dados.get('percentual_restante', ''),
                        '',
                        '',
                        ''
                    ])
                elif tipo == 'alerta':
                    writer.writerow([
                        timestamp_recebimento,
                        'ALERTA',
                        dados.get('produto_id', ''),
                        dados.get('produto_nome', ''),
                        dados.get('peso_atual', ''),
                        '',
                        '',
                        dados.get('peso_critico', ''),
                        dados.get('tipo', ''),
                        dados.get('mensagem', '')
                    ])
        except Exception as e:
            print(f"[ERRO] Falha ao salvar no CSV: {e}")
    
    def _calcular_estado(self, peso_atual_kg, peso_minimo_kg, peso_ideal_kg):
        """Calcula o estado do estoque baseado no peso atual, mínimo e ideal"""
        if peso_atual_kg <= peso_minimo_kg:
            return 'CRITICO'
        elif peso_atual_kg <= peso_ideal_kg:
            return 'BAIXO'
        else:
            return 'IDEAL'
    
    def _enviar_via_websocket(self, evento, dados):
        """Envia dados via WebSocket para todos os clientes conectados"""
        try:
            # Envia para todos os clientes conectados (sem room = broadcast para todos)
            self.socketio.emit(evento, dados)
            print(f"[WEBSOCKET] Evento '{evento}' enviado: {dados.get('Produto', dados.get('produto_nome', 'N/A'))}")
        except Exception as e:
            print(f"[ERRO] Falha ao enviar via WebSocket: {e}")
            import traceback
            traceback.print_exc()
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback quando conecta ao broker"""
        if rc == 0:
            print(f"[CONECTADO] Broker MQTT: {self.broker_host}:{self.broker_port}")
            client.subscribe(TOPIC_SUBSCRIBE, qos=1)
            print(f"[INSCRITO] Tópico: {TOPIC_SUBSCRIBE}")
        else:
            print(f"[ERRO] Falha na conexão. Código: {rc}")
    
    def on_subscribe(self, client, userdata, mid, granted_qos):
        """Callback quando se inscreve em um topico"""
        print(f"[INFO] Inscrição confirmada (QoS: {granted_qos[0]})")
        print("=" * 70)
        print("[AGUARDANDO] Dados dos sensores...")
        print("=" * 70)
    
    def on_message(self, client, userdata, msg):
        """Callback quando recebe uma mensagem"""
        try:
            dados = json.loads(msg.payload.decode('utf-8'))
            topico = msg.topic
            
            if 'alerta' in topico:
                self.processar_alerta(dados)
            else:
                self.processar_medicao(dados)
                
        except json.JSONDecodeError as e:
            print(f"[ERRO] Falha ao decodificar JSON: {e}")
        except Exception as e:
            print(f"[ERRO] Erro ao processar mensagem: {e}")
    
    def processar_medicao(self, dados):
        """Processa uma leitura de peso"""
        produto_id = dados.get('produto_id')
        
        with self.lock:
            self.leituras_recebidas += 1
            
            # Verifica se produto existe nos cadastrados
            if produto_id not in self.produtos_cadastrados:
                print(f"[AVISO] Produto ID {produto_id} não cadastrado. Ignorando leitura.")
                return
            
            produto_cadastrado = self.produtos_cadastrados[produto_id]
            produto_nome = produto_cadastrado['nome']
            peso_gramas = dados.get('peso_gramas', 0)
            timestamp = dados.get('timestamp', '')
            
            # Converte gramas para KG
            peso_atual_kg = peso_gramas / 1000
            peso_minimo_kg = produto_cadastrado['pesoMinimo']
            peso_maximo_kg = produto_cadastrado['pesoMaximo']
            peso_ideal_kg = produto_cadastrado.get('pesoIdeal', peso_minimo_kg * 2)
            
            # Calcula estado
            estado = self._calcular_estado(peso_atual_kg, peso_minimo_kg, peso_ideal_kg)
            
            # Prepara dados para WebSocket
            dados_produto = {
                'produto': produto_nome,
                'peso_minimo': peso_minimo_kg,
                'peso_maximo': peso_maximo_kg,
                'peso_atual': round(peso_atual_kg, 2),
                'peso_ideal': round(peso_ideal_kg, 2),
                'ultima_atualizacao': timestamp
            }
            
            # Armazena dados do produto
            self.produtos_dados[produto_id] = dados_produto
        
        # Envia via WebSocket **fora do lock para evitar deadlock
        self._enviar_via_websocket('produto_atualizado', dados_produto)
        
        # Exibe no console
        print(f"\n[📊 LEITURA #{self.leituras_recebidas}]")
        print(f"   {produto_nome}: {peso_atual_kg:.2f}kg - Estado: {estado}")

        self.salvar_csv(dados, tipo='peso')
    
    def processar_alerta(self, dados):
        """Processa um alerta de reposição"""
        with self.lock:
            self.alertas_recebidos += 1
            produto_id = dados.get('produto_id')
            
            if produto_id not in self.produtos_cadastrados:
                return
            
            produto_cadastrado = self.produtos_cadastrados[produto_id]
            produto_nome = produto_cadastrado['nome']
            peso_atual = dados.get('peso_atual', 0)
            peso_critico = dados.get('peso_critico', 0)
            mensagem = dados.get('mensagem', 'Alerta de reposição')
            timestamp = dados.get('timestamp', '')
            
            alerta = {
                'produto_id': produto_id,
                'produto_nome': produto_nome,
                'peso_atual': round(peso_atual / 1000, 2),
                'peso_critico': round(peso_critico / 1000, 2),
                'peso_ideal': round(peso_critico / 1000, 2),
                'tipo': dados.get('tipo', 'REPOSICAO_URGENTE'),
                'mensagem': mensagem,
                'timestamp': timestamp
            }
            
        
        # Envia alerta via WebSocket (fora do lock)
        self._enviar_via_websocket('alerta', alerta)
        
        # Exibe alerta destacado
        print(f"\n{'=' * 70}")
        print(f"⚠️  [ALERTA #{self.alertas_recebidos}] ⚠️")
        print(f"{'=' * 70}")
        print(f"   {mensagem}")
        print(f"   Produto: {produto_nome}")
        print(f"   Peso atual: {alerta['peso_atual']:.2f}kg")
        print(f"   Timestamp: {timestamp}")
        print(f"{'=' * 70}\n")

        self.salvar_csv(dados, tipo='alerta')
    
    def _conectar_publisher(self):
        """Conecta o cliente MQTT publisher para simulações manuais"""
        def on_connect_pub(client, userdata, flags, rc):
            if rc == 0:
                self.client_publisher_connected = True
                print(f"[PUBLISHER] Cliente MQTT publisher conectado")
            else:
                self.client_publisher_connected = False
        
        try:
            self.client_publisher.on_connect = on_connect_pub
            self.client_publisher.connect(self.broker_host, self.broker_port, 60)
            self.client_publisher.loop_start()
            # Aguarda conexão
            for i in range(10):
                if self.client_publisher_connected:
                    break
                time.sleep(0.2)
            return self.client_publisher_connected
        except Exception as e:
            print(f"[ERRO] Falha ao conectar publisher: {e}")
            return False
    
    def _atualizar_sensor_publicador(self, produto_id, quantidade_kg, tipo_operacao):
        """Atualiza o sensor no publicador via API"""
        try:
            endpoint = f"{self.publicador_api_url}/api/sensores/{produto_id}/{tipo_operacao}"
            response = requests.post(
                endpoint,
                json={'quantidade': quantidade_kg},
                timeout=3
            )
            if response.status_code == 200:
                print(f"[PUBLICADOR] Sensor atualizado: {tipo_operacao} de {quantidade_kg:.2f}kg")
                return True
            else:
                print(f"[AVISO] Falha ao atualizar sensor no publicador. Status: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"[AVISO] Não foi possível conectar ao publicador: {e}")
            print(f"[AVISO] Certifique-se de que o publicador está rodando em {self.publicador_api_url}")
            return False
    
    def _publicar_simulacao(self, produto_id, peso_novo_kg):
        """Publica uma mensagem MQTT simulando uma leitura de sensor"""
        if produto_id not in self.produtos_cadastrados:
            return False
        
        produto = self.produtos_cadastrados[produto_id]
        topic = produto['topic']
        peso_gramas = peso_novo_kg * 1000
        peso_inicial = produto['pesoMaximo'] * 1000
        percentual_restante = (peso_gramas / peso_inicial) * 100 if peso_inicial > 0 else 0
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        dados = {
            "produto_id": produto_id,
            "produto_nome": produto['nome'],
            "peso_gramas": round(peso_gramas, 2),
            "peso_inicial": peso_inicial,
            "percentual_restante": round(percentual_restante, 2),
            "timestamp": timestamp
        }
        
        mensagem = json.dumps(dados, ensure_ascii=False)
        try:
            result = self.client_publisher.publish(topic, mensagem, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[SIMULAÇÃO] Publicada leitura para {produto['nome']}: {peso_novo_kg:.2f}kg")
                return True
            else:
                print(f"[ERRO] Falha ao publicar simulação. Código: {result.rc}")
                return False
        except Exception as e:
            print(f"[ERRO] Erro ao publicar simulação: {e}")
            return False
    
    def conectar(self):
        """Conecta ao broker MQTT"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            # Conecta também o publisher
            self._conectar_publisher()
            return True
        except Exception as e:
            print(f"[ERRO] Não foi possível conectar ao broker: {e}")
            print(f"[INFO] Certifique-se de que um broker MQTT está rodando em {self.broker_host}:{self.broker_port}")
            return False
    
    def _configurar_rotas(self):
        """Configura as rotas da API REST"""
        
        @self.app.route('/api/ping', methods=['GET'])
        def ping():
            return jsonify({'status': 'ok', 'message': 'pong'})
        
        @self.app.route('/api/produtos', methods=['POST'])
        def cadastrar_produto():
            """Cadastra um novo produto para simulação"""
            try:
                data = request.get_json()
                
                # Validação dos campos obrigatórios
                if not data or 'nome' not in data:
                    return jsonify({'erro': 'Campo "nome" é obrigatório'}), 400
                
                nome = data.get('nome')
                peso_minimo = float(data.get('pesoMinimo', 100))  # KG
                peso_maximo = float(data.get('pesoMaximo', 1000))  # KG
                peso_ideal = float(data.get('pesoIdeal', peso_minimo * 2))  # KG
                topic = data.get('topic', None)  # Opcional
                
                # Validação de valores
                if peso_minimo <= 0 or peso_maximo <= 0 or peso_ideal <= 0:
                    return jsonify({'erro': 'Pesos devem ser maiores que zero'}), 400
                
                if peso_minimo >= peso_maximo:
                    return jsonify({'erro': 'pesoMinimo deve ser menor que pesoMaximo'}), 400
                
                if peso_ideal < peso_minimo or peso_ideal > peso_maximo:
                    return jsonify({'erro': 'pesoIdeal deve estar entre pesoMinimo e pesoMaximo'}), 400
                
                with self.lock:
                    # Validação: verifica se já existe produto com o mesmo nome
                    for produto_existente in self.produtos_cadastrados.values():
                        if produto_existente['nome'].lower() == nome.lower():
                            return jsonify({'erro': f'Já existe um produto com o nome "{nome}"'}), 409
                    
                    # Determina o tópico (gera automaticamente se não informado)
                    topic_final = topic if topic else f"{TOPIC_BASE}/produto{self.next_produto_id}/peso"
                    
                    # Validação: verifica se já existe produto com o mesmo tópico
                    for produto_existente in self.produtos_cadastrados.values():
                        if produto_existente['topic'] == topic_final:
                            return jsonify({'erro': f'Já existe um produto usando o tópico "{topic_final}"'}), 409
                    
                    produto_id = self.next_produto_id
                    self.next_produto_id += 1
                    
                    produto = {
                        'produto_id': produto_id,
                        'nome': nome,
                        'pesoMinimo': peso_minimo,
                        'pesoMaximo': peso_maximo,
                        'pesoIdeal': peso_ideal,
                        'topic': topic_final
                    }
                    
                    self.produtos_cadastrados[produto_id] = produto
                    
                    print(f"[INFO] Produto cadastrado: ID {produto_id} - {nome} (tópico: {topic_final})")
                
                return jsonify(produto), 201
                
            except ValueError as e:
                return jsonify({'erro': f'Valor inválido: {str(e)}'}), 400
            except Exception as e:
                return jsonify({'erro': f'Erro ao cadastrar produto: {str(e)}'}), 500
        
        @self.app.route('/api/produtos', methods=['GET'])
        def listar_produtos_cadastrados():
            """Lista todos os produtos cadastrados"""
            with self.lock:
                produtos = list(self.produtos_cadastrados.values())
                return jsonify(produtos)
        
        @self.app.route('/api/produtos/<int:produto_id>', methods=['DELETE'])
        def remover_produto(produto_id):
            """Remove um produto cadastrado"""
            with self.lock:
                if produto_id not in self.produtos_cadastrados:
                    return jsonify({'erro': 'Produto não encontrado'}), 404
                
                produto = self.produtos_cadastrados.pop(produto_id)
                if produto_id in self.produtos_dados:
                    del self.produtos_dados[produto_id]
                
                print(f"[INFO] Produto removido: ID {produto_id} - {produto['nome']}")
                return jsonify({'mensagem': 'Produto removido com sucesso'}), 200
        
        @self.app.route('/api/produtos/<int:produto_id>/retirada', methods=['POST'])
        def simular_retirada(produto_id):
            """Simula retirada manual de produtos - centralizado no backend"""
            try:
                data = request.get_json() or {}
                quantidade_kg = float(data.get('quantidade', 0))  # Quantidade em KG
                
                with self.lock:
                    if produto_id not in self.produtos_cadastrados:
                        return jsonify({'erro': 'Produto não encontrado'}), 404
                    
                    produto = self.produtos_cadastrados[produto_id]
                    
                    # Obtém peso atual do produto (se existir)
                    if produto_id in self.produtos_dados:
                        peso_atual_kg = self.produtos_dados[produto_id].get('pesoAtual', produto['pesoMaximo'])
                    else:
                        peso_atual_kg = produto['pesoMaximo']
                    
                    # Se quantidade não foi especificada, usa valor aleatório (5-15% do peso atual)
                    if quantidade_kg <= 0:
                        quantidade_kg = peso_atual_kg * random.uniform(0.05, 0.15)
                    
                    # Calcula novo peso
                    peso_novo_kg = max(0, peso_atual_kg - quantidade_kg)
                
                # 1. Atualiza o sensor no publicador (reflete na balança real)
                sensor_atualizado = self._atualizar_sensor_publicador(produto_id, quantidade_kg, 'retirada')
                
                # 2. Publica mensagem MQTT (o sensor também publicará na próxima iteração)
                mqtt_publicado = self._publicar_simulacao(produto_id, peso_novo_kg)
                
                if sensor_atualizado or mqtt_publicado:
                    return jsonify({
                        'mensagem': 'Retirada executada com sucesso',
                        'produto_id': produto_id,
                        'produto_nome': produto['nome'],
                        'peso_anterior': round(peso_atual_kg, 2),
                        'quantidade_retirada': round(quantidade_kg, 2),
                        'peso_novo': round(peso_novo_kg, 2),
                        'sensor_atualizado': sensor_atualizado,
                        'mqtt_publicado': mqtt_publicado
                    }), 200
                else:
                    return jsonify({'erro': 'Falha ao executar retirada. Verifique se o publicador está rodando.'}), 500
                    
            except ValueError as e:
                return jsonify({'erro': f'Valor inválido: {str(e)}'}), 400
            except Exception as e:
                return jsonify({'erro': f'Erro ao simular retirada: {str(e)}'}), 500
        
        @self.app.route('/api/produtos/<int:produto_id>/reposicao', methods=['POST'])
        def simular_reposicao(produto_id):
            """Simula reposição manual de produtos - centralizado no backend"""
            try:
                data = request.get_json() or {}
                quantidade_kg = float(data.get('quantidade', 0))  # Quantidade em KG
                
                with self.lock:
                    if produto_id not in self.produtos_cadastrados:
                        return jsonify({'erro': 'Produto não encontrado'}), 404
                    
                    produto = self.produtos_cadastrados[produto_id]

                    if produto_id in self.produtos_dados:
                        peso_atual_kg = self.produtos_dados[produto_id].get('pesoAtual', 0)
                    else:
                        peso_atual_kg = 0

                    # Se quantidade não foi especificada, usa um valor aleatório 1 a 5kg
                    if quantidade_kg <= 0:
                        quantidade_kg = random.uniform(1, 5)
                    
                    # Calcula novo peso sem ultrapassar o máximo
                    peso_novo_kg = min(produto['pesoMaximo'], peso_atual_kg + quantidade_kg)

                sensor_atualizado = self._atualizar_sensor_publicador(produto_id, quantidade_kg, 'reposicao')
                mqtt_publicado = self._publicar_simulacao(produto_id, peso_novo_kg)
                
                if sensor_atualizado or mqtt_publicado:
                    return jsonify({
                        'mensagem': 'Reposição executada com sucesso',
                        'produto_id': produto_id,
                        'produto_nome': produto['nome'],
                        'peso_anterior': round(peso_atual_kg, 2),
                        'quantidade_adicionada': round(quantidade_kg, 2),
                        'peso_novo': round(peso_novo_kg, 2),
                        'sensor_atualizado': sensor_atualizado,
                        'mqtt_publicado': mqtt_publicado
                    }), 200
                else:
                    return jsonify({'erro': 'Falha ao executar reposição. Verifique se o publicador está rodando.'}), 500
                    
            except ValueError as e:
                return jsonify({'erro': f'Valor inválido: {str(e)}'}), 400
            except Exception as e:
                return jsonify({'erro': f'Erro ao simular reposição: {str(e)}'}), 500
    
    def _configurar_websocket(self):
        """Configura eventos do WebSocket"""
        
        @self.socketio.on('connect')
        def handle_connect(auth):
            print(f"[WEBSOCKET] Cliente conectado (auth: {auth})")
            try:
                # Obtém lista de produtos
                with self.lock:
                    produtos_list = list(self.produtos_dados.values())
                    num_produtos = len(produtos_list)

                if num_produtos > 0:
                    print(f"[WEBSOCKET] Enviando {num_produtos} produto(s) iniciais")
                    emit('produtos_iniciais', produtos_list)
                else:
                    print(f"[WEBSOCKET] Nenhum produto com dados ainda. Enviando lista vazia para confirmar conexão.")
                    emit('produtos_iniciais', [])
                    emit('teste', {'mensagem': 'WebSocket funcionando!'})
            except Exception as e:
                print(f"[ERRO] Falha ao enviar produtos iniciais: {e}")
                import traceback
                traceback.print_exc()
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            print(f"[WEBSOCKET] Cliente desconectado")
        
        @self.socketio.on_error_default
        def default_error_handler(e):
            print(f"[WEBSOCKET] Erro: {e}")
            import traceback
            traceback.print_exc()
    
    def _iniciar_api(self):
        """Inicia o servidor Flask + SocketIO em thread separada"""
        def run_api():
            self.socketio.run(self.app, host=self.api_host, port=self.api_port, 
                            debug=False, allow_unsafe_werkzeug=True, use_reloader=False)
        
        thread = Thread(target=run_api, daemon=True)
        thread.start()
        print(f"[API] Servidor iniciado em http://{self.api_host}:{self.api_port}")
        print(f"[API] WebSocket disponível em ws://{self.api_host}:{self.api_port}")
        print(f"[API] Endpoints disponíveis:")
        print(f"       GET  /api/ping - Status do servidor")
        print(f"       POST /api/produtos - Cadastrar produto")
        print(f"       GET  /api/produtos - Listar produtos cadastrados")
        print(f"       DELETE /api/produtos/<id> - Remover produto")
        print(f"       POST /api/produtos/<id>/retirada - Retirar peso (atualiza sensor + MQTT)")
        print(f"       POST /api/produtos/<id>/reposicao - Repor peso (atualiza sensor + MQTT)")
        print(f"[API] Publicador: {self.publicador_api_url}")
    
    def executar(self):
        """Executa o servidor backend (MQTT + WebSocket)"""
        print("=" * 70)
        print("SERVIDOR BACKEND - MQTT + WebSocket")
        print("=" * 70)
        print(f"Broker MQTT: {self.broker_host}:{self.broker_port}")
        print(f"Tópico: {TOPIC_SUBSCRIBE}")
        print(f"API/WebSocket: http://{self.api_host}:{self.api_port}")
        print(f"Publicador API: {self.publicador_api_url}")
        print(f"Arquivo CSV: {self.arquivo_csv}")
        print("=" * 70)
        
        # Inicia API/WebSocket
        self._iniciar_api()
        time.sleep(2)  # Aguarda servidor iniciar
        
        if self.conectar():
            try:
                print("\n[INFO] Backend ativo. Pressione Ctrl+C para parar.\n")
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n[INFO] Encerrando servidor...")
                print(f"[ESTATÍSTICAS] Leituras recebidas: {self.leituras_recebidas}")
                print(f"[ESTATÍSTICAS] Alertas recebidos: {self.alertas_recebidos}")
                print(f"[INFO] Dados salvos em: {self.arquivo_csv}")
                self.client.loop_stop()
                self.client.disconnect()
                if self.client_publisher_connected:
                    self.client_publisher.loop_stop()
                    self.client_publisher.disconnect()
                print("[INFO] Servidor encerrado.")
        else:
            print("[ERRO] Não foi possível iniciar o servidor.")


def main():
    parser = argparse.ArgumentParser(
        description="Servidor backend que recebe dados MQTT e expõe WebSocket"
    )
    parser.add_argument(
        "--broker",
        default=BROKER_HOST,
        help=f"Endereço do broker MQTT (padrão: {BROKER_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=BROKER_PORT,
        help=f"Porta do broker MQTT (padrão: {BROKER_PORT})"
    )
    parser.add_argument(
        "--csv",
        default=ARQUIVO_CSV,
        help=f"Arquivo CSV para salvar dados (padrão: {ARQUIVO_CSV})"
    )
    parser.add_argument(
        "--api-host",
        default=API_HOST,
        help=f"Host da API/WebSocket (padrão: {API_HOST})"
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=API_PORT,
        help=f"Porta da API/WebSocket (padrão: {API_PORT})"
    )
    parser.add_argument(
        "--publicador-api-url",
        default=PUBLICADOR_API_URL,
        help=f"URL da API do publicador (padrão: {PUBLICADOR_API_URL})"
    )
    
    args = parser.parse_args()
    
    servidor = ServidorBackend(
        broker_host=args.broker,
        broker_port=args.port,
        arquivo_csv=args.csv,
        api_host=args.api_host,
        api_port=args.api_port,
        publicador_api_url=args.publicador_api_url
    )
    
    servidor.executar()


if __name__ == "__main__":
    main()