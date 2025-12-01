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
from sqlalchemy.exc import SQLAlchemyError

# Imports locais
from models import db, Produto, Leitura, Alerta, init_db
from config import (
    DATABASE_URL, BROKER_HOST, BROKER_PORT, TOPIC_BASE,
    API_HOST, API_PORT, PUBLICADOR_API_URL, ARQUIVO_CSV
)

TOPIC_SUBSCRIBE = f"{TOPIC_BASE}/#"


"""
Servidor Backend - Coletor MQTT + WebSocket + API REST
Recebe dados MQTT de sensores de produtos e expõe WebSocket para frontend
"""

class ServidorBackend:
    """Classe que gerencia o servidor coletor de dados MQTT"""
    
    def __init__(self, broker_host, broker_port, arquivo_csv, api_host, api_port, publicador_api_url, database_url):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.arquivo_csv = arquivo_csv
        self.api_host = api_host
        self.api_port = api_port
        self.publicador_api_url = publicador_api_url
        self.database_url = database_url
        
        # Cliente MQTT (assinante)
        self.client = mqtt.Client(client_id="servidor_coletor")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        
        # Cliente MQTT para publicação (simulação manual)
        self.client_publisher = mqtt.Client(client_id="servidor_coletor_publisher")
        self.client_publisher_connected = False
        
        # Armazenamento em memória (cache para WebSocket - dados em tempo real)
        self.lock = Lock()
        self.produtos_dados = {}  # Cache em memória para dados atuais (WebSocket)
        
        # Flask + SocketIO
        self.app = Flask(__name__)
        
        # Configuração do banco de dados
        self.app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        
        # Inicializa banco de dados (com retry para aguardar PostgreSQL estar pronto)
        try:
            init_db(self.app)
            print(f"[DB] ✅ Banco de dados conectado: {database_url.split('@')[-1] if '@' in database_url else database_url}")
        except Exception as e:
            print(f"[DB] ⚠️ Aviso: Erro ao inicializar banco: {e}")
            print(f"[DB] ⚠️ O sistema continuará, mas algumas funcionalidades podem não funcionar até o banco estar disponível")
        
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
        
        # Carrega produtos do banco na inicialização
        self._carregar_produtos_do_banco()
        
        self.inicializar_csv()
    
    def _carregar_produtos_do_banco(self):
        """Carrega produtos cadastrados do banco de dados na inicialização"""
        try:
            with self.app.app_context():
                produtos = Produto.query.all()
                print(f"[DB] ✅ Carregados {len(produtos)} produto(s) do banco de dados")
                for produto in produtos:
                    print(f"[DB]   - ID {produto.produto_id}: {produto.nome} (tópico: {produto.topic})")
                    # Carrega última leitura para dados em tempo real
                    ultima_leitura = Leitura.query.filter_by(produto_id=produto.produto_id).order_by(Leitura.timestamp_recebimento.desc()).first()
                    if ultima_leitura:
                        timestamp_str = ultima_leitura.timestamp_sensor.strftime("%Y-%m-%d %H:%M:%S") if ultima_leitura.timestamp_sensor else ultima_leitura.timestamp_recebimento.strftime("%Y-%m-%d %H:%M:%S")
                        self.produtos_dados[produto.produto_id] = {
                            'produto': produto.nome,
                            'peso_minimo': produto.peso_minimo,
                            'peso_maximo': produto.peso_maximo,
                            'peso_ideal': produto.peso_ideal,
                            'peso_atual': ultima_leitura.peso_kg,
                            'ultima_atualizacao': timestamp_str
                        }
                    else:
                        # Se não houver leitura, inicializa com peso máximo
                        self.produtos_dados[produto.produto_id] = {
                            'produto': produto.nome,
                            'peso_minimo': produto.peso_minimo,
                            'peso_maximo': produto.peso_maximo,
                            'peso_ideal': produto.peso_ideal,
                            'peso_atual': produto.peso_maximo,
                            'ultima_atualizacao': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        print(f"[DB]   - Produto {produto.nome} sem leituras anteriores, usando peso máximo: {produto.peso_maximo}kg")
        except Exception as e:
            print(f"[ERRO] ❌ Falha ao carregar produtos do banco: {e}")
            import traceback
            traceback.print_exc()
    
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
            # Não precisa especificar namespace quando usando socketio.emit diretamente
            self.socketio.emit(evento, dados)
            # Tenta obter o nome do produto de diferentes formas possíveis
            nome_produto = dados.get('produto') or dados.get('produto_nome') or dados.get('Produto') or 'N/A'
            print(f"[WEBSOCKET] ✅ Evento '{evento}' enviado: {nome_produto}")
        except Exception as e:
            print(f"[ERRO] ❌ Falha ao enviar via WebSocket: {e}")
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
        peso_gramas = dados.get('peso_gramas', 0)
        timestamp_str = dados.get('timestamp', '')
        
        try:
            # Converte timestamp string para datetime
            timestamp_dt = None
            if timestamp_str:
                try:
                    timestamp_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except:
                    timestamp_dt = datetime.utcnow()
            else:
                timestamp_dt = datetime.utcnow()
            
            with self.app.app_context():
                # Busca produto no banco
                produto = Produto.query.get(produto_id)
                if not produto:
                    print(f"[AVISO] Produto ID {produto_id} não cadastrado. Ignorando leitura.")
                    return
                
                # Converte gramas para KG
                peso_atual_kg = peso_gramas / 1000
                
                # Calcula estado
                estado = self._calcular_estado(peso_atual_kg, produto.peso_minimo, produto.peso_ideal)
                
                # Salva leitura no banco
                leitura = Leitura(
                    produto_id=produto_id,
                    peso_gramas=peso_gramas,
                    peso_kg=peso_atual_kg,
                    peso_inicial=dados.get('peso_inicial'),
                    percentual_restante=dados.get('percentual_restante'),
                    timestamp_sensor=timestamp_dt
                )
                db.session.add(leitura)
                db.session.commit()
                
                # Prepara dados para WebSocket
                dados_produto = {
                    'produto': produto.nome,
                    'peso_minimo': produto.peso_minimo,
                    'peso_maximo': produto.peso_maximo,
                    'peso_atual': round(peso_atual_kg, 2),
                    'peso_ideal': produto.peso_ideal,
                    'ultima_atualizacao': timestamp_str
                }
                
                # Atualiza cache em memória
                with self.lock:
                    self.produtos_dados[produto_id] = dados_produto
            
            # Envia via WebSocket **fora do lock para evitar deadlock
            self._enviar_via_websocket('produto_atualizado', dados_produto)
            
            # Exibe no console
            print(f"\n[📊 LEITURA] {produto.nome}: {peso_atual_kg:.2f}kg - Estado: {estado}")

            self.salvar_csv(dados, tipo='peso')
            
        except SQLAlchemyError as e:
            print(f"[ERRO DB] Falha ao salvar leitura: {e}")
            db.session.rollback()
        except Exception as e:
            print(f"[ERRO] Erro ao processar medição: {e}")
            import traceback
            traceback.print_exc()
    
    def processar_alerta(self, dados):
        """Processa um alerta de reposição"""
        produto_id = dados.get('produto_id')
        peso_atual_gramas = dados.get('peso_atual', 0)
        peso_critico_gramas = dados.get('peso_critico', 0)
        mensagem = dados.get('mensagem', 'Alerta de reposição')
        timestamp_str = dados.get('timestamp', '')
        
        try:
            # Converte timestamp string para datetime
            timestamp_dt = None
            if timestamp_str:
                try:
                    timestamp_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except:
                    timestamp_dt = datetime.utcnow()
            else:
                timestamp_dt = datetime.utcnow()
            
            with self.app.app_context():
                # Busca produto no banco
                produto = Produto.query.get(produto_id)
                if not produto:
                    print(f"[AVISO] Produto ID {produto_id} não cadastrado. Ignorando alerta.")
                    return
                
                peso_atual_kg = peso_atual_gramas / 1000
                peso_critico_kg = peso_critico_gramas / 1000
                
                # Salva alerta no banco
                alerta_db = Alerta(
                    produto_id=produto_id,
                    tipo=dados.get('tipo', 'REPOSICAO_URGENTE'),
                    mensagem=mensagem,
                    peso_atual_kg=peso_atual_kg,
                    peso_critico_kg=peso_critico_kg,
                    timestamp_sensor=timestamp_dt
                )
                db.session.add(alerta_db)
                db.session.commit()
                
                alerta = {
                    'produto_id': produto_id,
                    'produto_nome': produto.nome,
                    'peso_atual': round(peso_atual_kg, 2),
                    'peso_critico': round(peso_critico_kg, 2),
                    'peso_ideal': round(peso_critico_kg, 2),
                    'tipo': dados.get('tipo', 'REPOSICAO_URGENTE'),
                    'mensagem': mensagem,
                    'timestamp': timestamp_str
                }
            
            # Envia alerta via WebSocket
            self._enviar_via_websocket('alerta', alerta)
            
            # Exibe alerta destacado
            print(f"\n{'=' * 70}")
            print(f"⚠️  [ALERTA] ⚠️")
            print(f"{'=' * 70}")
            print(f"   {mensagem}")
            print(f"   Produto: {produto.nome}")
            print(f"   Peso atual: {alerta['peso_atual']:.2f}kg")
            print(f"   Timestamp: {timestamp_str}")
            print(f"{'=' * 70}\n")

            self.salvar_csv(dados, tipo='alerta')
            
        except SQLAlchemyError as e:
            print(f"[ERRO DB] Falha ao salvar alerta: {e}")
            db.session.rollback()
        except Exception as e:
            print(f"[ERRO] Erro ao processar alerta: {e}")
            import traceback
            traceback.print_exc()
    
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
        try:
            with self.app.app_context():
                produto = Produto.query.get(produto_id)
                if not produto:
                    return False
                
                topic = produto.topic
                peso_gramas = peso_novo_kg * 1000
                peso_inicial = produto.peso_maximo * 1000
                percentual_restante = (peso_gramas / peso_inicial) * 100 if peso_inicial > 0 else 0
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                
                dados = {
                    "produto_id": produto_id,
                    "produto_nome": produto.nome,
                    "peso_gramas": round(peso_gramas, 2),
                    "peso_inicial": peso_inicial,
                    "percentual_restante": round(percentual_restante, 2),
                    "timestamp": timestamp
                }
                
                mensagem = json.dumps(dados, ensure_ascii=False)
                try:
                    result = self.client_publisher.publish(topic, mensagem, qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        print(f"[SIMULAÇÃO] Publicada leitura para {produto.nome}: {peso_novo_kg:.2f}kg")
                        return True
                    else:
                        print(f"[ERRO] Falha ao publicar simulação. Código: {result.rc}")
                        return False
                except Exception as e:
                    print(f"[ERRO] Erro ao publicar simulação: {e}")
                    return False
        except Exception as e:
            print(f"[ERRO] Erro ao buscar produto para simulação: {e}")
            return False
    
    def conectar(self):
        """Conecta ao broker MQTT"""
        try:
            print(f"[MQTT] Tentando conectar ao broker {self.broker_host}:{self.broker_port}...")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # Aguarda um pouco para verificar se conectou
            time.sleep(1)
            
            # Tenta conectar também o publisher (não crítico)
            self._conectar_publisher()
            
            print(f"[MQTT] ✅ Conectado ao broker {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            print(f"[ERRO] Não foi possível conectar ao broker: {e}")
            print(f"[INFO] Certifique-se de que um broker MQTT está rodando em {self.broker_host}:{self.broker_port}")
            print(f"[INFO] Ou configure BROKER_HOST no docker-compose.yml para um broker acessível")
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
                
                with self.app.app_context():
                    try:
                        # Validação: verifica se já existe produto com o mesmo nome
                        if Produto.query.filter(Produto.nome.ilike(nome)).first():
                            return jsonify({'erro': f'Já existe um produto com o nome "{nome}"'}), 409
                        
                        # Determina o tópico (gera automaticamente se não informado)
                        if not topic:
                            # Busca o maior ID para gerar próximo
                            ultimo_produto = Produto.query.order_by(Produto.produto_id.desc()).first()
                            proximo_id = (ultimo_produto.produto_id + 1) if ultimo_produto else 1
                            topic_final = f"{TOPIC_BASE}/produto{proximo_id}/peso"
                        else:
                            topic_final = topic
                        
                        # Validação: verifica se já existe produto com o mesmo tópico
                        if Produto.query.filter_by(topic=topic_final).first():
                            return jsonify({'erro': f'Já existe um produto usando o tópico "{topic_final}"'}), 409
                        
                        # Cria produto no banco
                        produto = Produto(
                            nome=nome,
                            peso_minimo=peso_minimo,
                            peso_maximo=peso_maximo,
                            peso_ideal=peso_ideal,
                            topic=topic_final
                        )
                        db.session.add(produto)
                        db.session.commit()
                        
                        # Recarrega o produto para garantir que o ID foi gerado
                        db.session.refresh(produto)
                        
                        print(f"[INFO] ✅ Produto cadastrado: ID {produto.produto_id} - {nome} (tópico: {topic_final})")
                        
                        return jsonify(produto.to_dict()), 201
                        
                    except SQLAlchemyError as e:
                        db.session.rollback()
                        print(f"[ERRO DB] Falha ao cadastrar produto: {e}")
                        import traceback
                        traceback.print_exc()
                        return jsonify({'erro': f'Erro no banco de dados: {str(e)}'}), 500
                    except Exception as e:
                        db.session.rollback()
                        print(f"[ERRO] Erro ao cadastrar produto: {e}")
                        import traceback
                        traceback.print_exc()
                        return jsonify({'erro': f'Erro ao cadastrar produto: {str(e)}'}), 500
                
            except ValueError as e:
                return jsonify({'erro': f'Valor inválido: {str(e)}'}), 400
            except Exception as e:
                print(f"[ERRO] Erro geral ao cadastrar produto: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'erro': f'Erro ao cadastrar produto: {str(e)}'}), 500
        
        @self.app.route('/api/produtos', methods=['GET'])
        def listar_produtos_cadastrados():
            """Lista todos os produtos cadastrados"""
            try:
                with self.app.app_context():
                    produtos = Produto.query.all()
                    return jsonify([p.to_dict() for p in produtos])
            except Exception as e:
                return jsonify({'erro': f'Erro ao listar produtos: {str(e)}'}), 500
        
        @self.app.route('/api/produtos/<int:produto_id>', methods=['DELETE'])
        def remover_produto(produto_id):
            """Remove um produto cadastrado"""
            try:
                with self.app.app_context():
                    produto = Produto.query.get(produto_id)
                    if not produto:
                        return jsonify({'erro': 'Produto não encontrado'}), 404
                    
                    nome_produto = produto.nome
                    db.session.delete(produto)
                    db.session.commit()
                    
                    # Remove do cache em memória
                    with self.lock:
                        if produto_id in self.produtos_dados:
                            del self.produtos_dados[produto_id]
                    
                    print(f"[INFO] Produto removido: ID {produto_id} - {nome_produto}")
                    return jsonify({'mensagem': 'Produto removido com sucesso'}), 200
            except SQLAlchemyError as e:
                db.session.rollback()
                return jsonify({'erro': f'Erro no banco de dados: {str(e)}'}), 500
            except Exception as e:
                return jsonify({'erro': f'Erro ao remover produto: {str(e)}'}), 500
        
        @self.app.route('/api/produtos/<int:produto_id>/retirada', methods=['POST'])
        def simular_retirada(produto_id):
            """Simula retirada manual de produtos - centralizado no backend"""
            try:
                data = request.get_json() or {}
                quantidade_kg = float(data.get('quantidade', 0))  # Quantidade em KG
                
                with self.app.app_context():
                    produto = Produto.query.get(produto_id)
                    if not produto:
                        return jsonify({'erro': 'Produto não encontrado'}), 404
                    
                    # Obtém peso atual do produto (cache ou máximo)
                    if produto_id in self.produtos_dados:
                        peso_atual_kg = self.produtos_dados[produto_id].get('peso_atual', produto.peso_maximo)
                    else:
                        peso_atual_kg = produto.peso_maximo
                    
                    # Se quantidade não foi especificada, usa valor aleatório (5-15% do peso atual)
                    if quantidade_kg <= 0:
                        quantidade_kg = peso_atual_kg * random.uniform(0.05, 0.15)
                    
                    # Calcula novo peso
                    peso_novo_kg = max(0, peso_atual_kg - quantidade_kg)
                
                # 1. Atualiza o sensor no publicador (reflete na balança real)
                sensor_atualizado = self._atualizar_sensor_publicador(produto_id, quantidade_kg, 'retirada')
                
                # 2. Atualiza dados localmente e envia via WebSocket imediatamente
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                dados_produto = {
                    'produto': produto.nome,
                    'peso_minimo': produto.peso_minimo,
                    'peso_maximo': produto.peso_maximo,
                    'peso_atual': round(peso_novo_kg, 2),
                    'peso_ideal': produto.peso_ideal,
                    'ultima_atualizacao': timestamp
                }
                
                with self.lock:
                    self.produtos_dados[produto_id] = dados_produto
                
                # Envia atualização via WebSocket
                self._enviar_via_websocket('produto_atualizado', dados_produto)
                
                # 3. Publica mensagem MQTT (o sensor também publicará na próxima iteração)
                mqtt_publicado = self._publicar_simulacao(produto_id, peso_novo_kg)
                
                if sensor_atualizado or mqtt_publicado:
                    return jsonify({
                        'mensagem': 'Retirada executada com sucesso',
                        'produto_id': produto_id,
                        'produto_nome': produto.nome,
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
                
                with self.app.app_context():
                    produto = Produto.query.get(produto_id)
                    if not produto:
                        return jsonify({'erro': 'Produto não encontrado'}), 404
                    
                    if produto_id in self.produtos_dados:
                        peso_atual_kg = self.produtos_dados[produto_id].get('peso_atual', 0)
                    else:
                        peso_atual_kg = 0

                    # Se quantidade não foi especificada, usa um valor aleatório 1 a 5kg
                    if quantidade_kg <= 0:
                        quantidade_kg = random.uniform(1, 5)
                    
                    # Calcula novo peso sem ultrapassar o máximo
                    peso_novo_kg = min(produto.peso_maximo, peso_atual_kg + quantidade_kg)

                # 1. Atualiza o sensor no publicador (reflete na balança real)
                sensor_atualizado = self._atualizar_sensor_publicador(produto_id, quantidade_kg, 'reposicao')
                
                # 2. Atualiza dados localmente e envia via WebSocket imediatamente
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                dados_produto = {
                    'produto': produto.nome,
                    'peso_minimo': produto.peso_minimo,
                    'peso_maximo': produto.peso_maximo,
                    'peso_atual': round(peso_novo_kg, 2),
                    'peso_ideal': produto.peso_ideal,
                    'ultima_atualizacao': timestamp
                }
                
                with self.lock:
                    self.produtos_dados[produto_id] = dados_produto
                
                # Envia atualização via WebSocket
                self._enviar_via_websocket('produto_atualizado', dados_produto)
                
                # 3. Publica mensagem MQTT (o sensor também publicará na próxima iteração)
                mqtt_publicado = self._publicar_simulacao(produto_id, peso_novo_kg)
                
                if sensor_atualizado or mqtt_publicado:
                    return jsonify({
                        'mensagem': 'Reposição executada com sucesso',
                        'produto_id': produto_id,
                        'produto_nome': produto.nome,
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
        def handle_connect():
            print(f"[WEBSOCKET] ✅ Cliente conectado")
            try:
                # Obtém lista de produtos
                with self.lock:
                    produtos_list = list(self.produtos_dados.values())
                    num_produtos = len(produtos_list)

                if num_produtos > 0:
                    print(f"[WEBSOCKET] 📦 Enviando {num_produtos} produto(s) iniciais")
                    emit('produtos_iniciais', produtos_list)
                    print(f"[WEBSOCKET] ✅ Produtos iniciais enviados")
                else:
                    print(f"[WEBSOCKET] ⚠️ Nenhum produto com dados ainda. Enviando lista vazia.")
                    emit('produtos_iniciais', [])
                    emit('teste', {'mensagem': 'WebSocket funcionando!'})
            except Exception as e:
                print(f"[ERRO] ❌ Falha ao enviar produtos iniciais: {e}")
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
        
        # Tenta conectar ao MQTT (mas continua mesmo se falhar)
        mqtt_conectado = self.conectar()
        if not mqtt_conectado:
            print("[AVISO] ⚠️ Não foi possível conectar ao broker MQTT.")
            print("[AVISO] A API REST e WebSocket continuarão funcionando normalmente.")
            print("[AVISO] Para receber dados MQTT, certifique-se de que o broker está acessível.")
        
        try:
            print("\n[INFO] ✅ Backend ativo. API REST e WebSocket disponíveis.")
            if mqtt_conectado:
                print("[INFO] ✅ Conexão MQTT estabelecida.")
            else:
                print("[INFO] ⚠️ MQTT não conectado - apenas API REST e WebSocket disponíveis.")
            print("[INFO] Pressione Ctrl+C para parar.\n")
            
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n[INFO] Encerrando servidor...")
            try:
                with self.app.app_context():
                    num_leituras = Leitura.query.count()
                    num_alertas = Alerta.query.count()
                    print(f"[ESTATÍSTICAS] Total de leituras no banco: {num_leituras}")
                    print(f"[ESTATÍSTICAS] Total de alertas no banco: {num_alertas}")
            except:
                pass
            print(f"[INFO] Dados salvos em: {self.arquivo_csv}")
            
            # Desconecta MQTT apenas se estava conectado
            try:
                if mqtt_conectado:
                    self.client.loop_stop()
                    self.client.disconnect()
            except:
                pass
            
            try:
                if self.client_publisher_connected:
                    self.client_publisher.loop_stop()
                    self.client_publisher.disconnect()
            except:
                pass
            
            print("[INFO] Servidor encerrado.")


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
    parser.add_argument(
        "--database-url",
        default=DATABASE_URL,
        help=f"URL do banco de dados (padrão: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL})"
    )
    
    args = parser.parse_args()
    
    servidor = ServidorBackend(
        broker_host=args.broker,
        broker_port=args.port,
        arquivo_csv=args.csv,
        api_host=args.api_host,
        api_port=args.api_port,
        publicador_api_url=args.publicador_api_url,
        database_url=args.database_url
    )
    
    servidor.executar()


if __name__ == "__main__":
    main()