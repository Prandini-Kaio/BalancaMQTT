import paho.mqtt.client as mqtt
import json
import csv
import os
import time
from datetime import datetime
import argparse
from threading import Thread, Lock
from flask import Flask, jsonify
from flask_cors import CORS
from collections import defaultdict

# Config padrao
BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883
TOPIC_BASE = "estoque"
TOPIC_SUBSCRIBE = f"{TOPIC_BASE}/#"
ARQUIVO_CSV = "dados.csv"
API_HOST = "0.0.0.0"
API_PORT = 5000


"""
Servidor Backend
"""

class ServidorBackend:
    """Classe que gerencia o servidor coletor de dados MQTT"""
    
    def __init__(self, broker_host, broker_port, arquivo_csv, api_host, api_port):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.arquivo_csv = arquivo_csv
        self.api_host = api_host
        self.api_port = api_port
        
        # Cliente MQTT
        self.client = mqtt.Client(client_id="servidor_coletor")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        
        # Armazenamento em memória
        self.lock = Lock()
        self.leituras_recebidas = 0
        self.alertas_recebidos = 0
        # Estrutura: {prateleira_id: {sensor_id: {última_leituras, peso_atual, etc}}}
        self.dados_prateleiras = defaultdict(lambda: defaultdict(dict))
        # Lista de alertas ativos
        self.alertas_ativos = []
        # Histórico de leituras (últimas 100 por sensor)
        self.historico = defaultdict(lambda: defaultdict(list))

        self.app = Flask(__name__)
        CORS(self.app)
        self._configurar_rotas()
        
        self.inicializar_csv()
    
    def inicializar_csv(self):
        """Cria o arquivo CSV com cabeçalho se não existir"""
        if not os.path.exists(self.arquivo_csv):
            with open(self.arquivo_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp_recebimento',
                    'tipo',
                    'prateleira_id',
                    'sensor_id',
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
                        dados.get('prateleira_id', ''),
                        dados.get('sensor_id', ''),
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
                        dados.get('prateleira_id', ''),
                        dados.get('sensor_id', ''),
                        dados.get('peso_atual', ''),
                        '',
                        '',
                        dados.get('peso_critico', ''),
                        dados.get('tipo', ''),
                        dados.get('mensagem', '')
                    ])
        except Exception as e:
            print(f"[ERRO] Falha ao salvar no CSV: {e}")
    
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
            # Decodifica a mensagem JSON
            dados = json.loads(msg.payload.decode('utf-8'))
            topico = msg.topic
            
            # Determina o tipo de mensagem (peso ou alerta)
            if 'alerta' in topico:
                self.processar_alerta(dados)
            else:
                self.processar_medicao(dados)
                
        except json.JSONDecodeError as e:
            print(f"[ERRO] Falha ao decodificar JSON: {e}")
            print(f"[DEBUG] Mensagem recebida: {msg.payload.decode('utf-8')}")
            print(f"[DEBUG] Tópico: {msg.topic}")
        except Exception as e:
            print(f"[ERRO] Erro ao processar mensagem: {e}")
            print(f"[DEBUG] Tópico: {msg.topic}")
            print(f"[DEBUG] Payload: {msg.payload.decode('utf-8', errors='ignore')}")
    
    def processar_medicao(self, dados):
        """Processa uma leitura de peso"""
        with self.lock:
            self.leituras_recebidas += 1
            prateleira_id = dados.get('prateleira_id')
            sensor_id = dados.get('sensor_id')
            peso = dados.get('peso_gramas', 0)
            percentual = dados.get('percentual_restante', 0)
            timestamp = dados.get('timestamp', '')
            
            # Armazena dados em memória
            self.dados_prateleiras[prateleira_id][sensor_id] = {
                'prateleira_id': prateleira_id,
                'sensor_id': sensor_id,
                'peso_atual': peso,
                'peso_inicial': dados.get('peso_inicial', 0),
                'percentual_restante': percentual,
                'timestamp': timestamp,
                'timestamp_recebimento': datetime.now().isoformat()
            }
            
            # Adiciona ao histórico (mantém últimas 100 leituras)
            self.historico[prateleira_id][sensor_id].append({
                'peso': peso,
                'percentual': percentual,
                'timestamp': timestamp
            })
            if len(self.historico[prateleira_id][sensor_id]) > 100:
                self.historico[prateleira_id][sensor_id].pop(0)
            
            # Remove alerta se peso voltou ao normal
            self.alertas_ativos = [
                a for a in self.alertas_ativos 
                if not (a.get('prateleira_id') == prateleira_id and a.get('sensor_id') == sensor_id)
            ]
        
        # Exibe no console
        print(f"\n[📊 LEITURA #{self.leituras_recebidas}]")
        print(f"   Prateleira: {prateleira_id} | Sensor: {sensor_id}")
        print(f"   Peso: {peso:.2f}g | Percentual restante: {percentual:.1f}%")
        print(f"   Timestamp: {timestamp}")

        self.salvar_csv(dados, tipo='peso')
    
    def processar_alerta(self, dados):
        """Processa um alerta de reposição"""
        with self.lock:
            self.alertas_recebidos += 1
            prateleira_id = dados.get('prateleira_id')
            sensor_id = dados.get('sensor_id')
            peso_atual = dados.get('peso_atual', 0)
            mensagem = dados.get('mensagem', 'Alerta de reposição')
            timestamp = dados.get('timestamp', '')
            
            # Adiciona alerta à lista (remove duplicatas do mesmo sensor)
            alerta = {
                'prateleira_id': prateleira_id,
                'sensor_id': sensor_id,
                'peso_atual': peso_atual,
                'peso_critico': dados.get('peso_critico', 0),
                'tipo': dados.get('tipo', 'REPOSICAO_URGENTE'),
                'mensagem': mensagem,
                'timestamp': timestamp,
                'timestamp_recebimento': datetime.now().isoformat()
            }
            
            # Remove alerta anterior do mesmo sensor se existir
            self.alertas_ativos = [
                a for a in self.alertas_ativos 
                if not (a.get('prateleira_id') == prateleira_id and a.get('sensor_id') == sensor_id)
            ]
            self.alertas_ativos.append(alerta)
        
        # Exibe alerta destacado
        print(f"\n{'=' * 70}")
        print(f"⚠️  [ALERTA #{self.alertas_recebidos}] ⚠️")
        print(f"{'=' * 70}")
        print(f"   {mensagem}")
        print(f"   Prateleira: {prateleira_id} | Sensor: {sensor_id}")
        print(f"   Peso atual: {peso_atual:.2f}g")
        print(f"   Timestamp: {timestamp}")
        print(f"{'=' * 70}\n")

        self.salvar_csv(dados, tipo='alerta')
    
    def conectar(self):
        """Conecta ao broker MQTT"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"[ERRO] Não foi possível conectar ao broker: {e}")
            print(f"[INFO] Certifique-se de que um broker MQTT está rodando em {self.broker_host}:{self.broker_port}")
            return False
    
    def _configurar_rotas(self):
        """Configura as rotas da API REST"""
        
        @self.app.route('/api/ping', methods=['GET'])
        def health():
            return jsonify({'status': 'ok', 'message': 'pong'})
        
        @self.app.route('/api/prateleiras', methods=['GET'])
        def listar_prateleiras():
            with self.lock:
                prateleiras = {}
                for prateleira_id, sensores in self.dados_prateleiras.items():
                    prateleiras[prateleira_id] = {
                        'prateleira_id': prateleira_id,
                        'num_sensores': len(sensores),
                        'sensores': list(sensores.keys())
                    }
                return jsonify(list(prateleiras.values()))
        
        @self.app.route('/api/prateleiras/<int:prateleira_id>', methods=['GET'])
        def obter_prateleira(prateleira_id):
            with self.lock:
                if prateleira_id not in self.dados_prateleiras:
                    return jsonify({'erro': 'Prateleira não encontrada'}), 404
                
                sensores = []
                for sensor_id, dados in self.dados_prateleiras[prateleira_id].items():
                    sensores.append(dados)
                
                return jsonify({
                    'prateleira_id': prateleira_id,
                    'num_sensores': len(sensores),
                    'sensores': sensores
                })
        
        @self.app.route('/api/sensores', methods=['GET'])
        def listar_sensores():
            with self.lock:
                sensores = []
                for prateleira_id, sensores_data in self.dados_prateleiras.items():
                    for sensor_id, dados in sensores_data.items():
                        sensores.append(dados)
                return jsonify(sensores)
        
        @self.app.route('/api/sensores/<int:prateleira_id>/<int:sensor_id>', methods=['GET'])
        def obter_sensor(prateleira_id, sensor_id):
            with self.lock:
                if (prateleira_id not in self.dados_prateleiras or 
                    sensor_id not in self.dados_prateleiras[prateleira_id]):
                    return jsonify({'erro': 'Sensor não encontrado'}), 404
                
                dados = self.dados_prateleiras[prateleira_id][sensor_id].copy()
                if prateleira_id in self.historico and sensor_id in self.historico[prateleira_id]:
                    dados['historico'] = self.historico[prateleira_id][sensor_id][-20:]  # Últimas 20 leituras
                
                return jsonify(dados)
        
        @self.app.route('/api/alertas', methods=['GET'])
        def listar_alertas():
            with self.lock:
                return jsonify(self.alertas_ativos)
        
        @self.app.route('/api/estatisticas', methods=['GET'])
        def obter_estatisticas():
            with self.lock:
                total_prateleiras = len(self.dados_prateleiras)
                total_sensores = sum(len(sensores) for sensores in self.dados_prateleiras.values())
                return jsonify({
                    'leituras_recebidas': self.leituras_recebidas,
                    'alertas_recebidos': self.alertas_recebidos,
                    'alertas_ativos': len(self.alertas_ativos),
                    'total_prateleiras': total_prateleiras,
                    'total_sensores': total_sensores
                })
    
    def _iniciar_api(self):
        """Inicia o servidor Flask em thread separada"""
        def run_api():
            self.app.run(host=self.api_host, port=self.api_port, debug=False, use_reloader=False)
        
        thread = Thread(target=run_api, daemon=True)
        thread.start()
        print(f"[API] Servidor REST iniciado em http://{self.api_host}:{self.api_port}")
        print(f"[API] Endpoints disponíveis:")
        print(f"       GET /api/health - Status do servidor")
        print(f"       GET /api/prateleiras - Lista todas as prateleiras")
        print(f"       GET /api/prateleiras/<id> - Dados de uma prateleira")
        print(f"       GET /api/sensores - Lista todos os sensores")
        print(f"       GET /api/sensores/<prateleira_id>/<sensor_id> - Dados de um sensor")
        print(f"       GET /api/alertas - Lista alertas ativos")
        print(f"       GET /api/estatisticas - Estatísticas gerais")
    
    def executar(self):
        """Executa o servidor backend (MQTT + API)"""
        print("=" * 70)
        print("SERVIDOR BACKEND - MQTT + API REST")
        print("=" * 70)
        print(f"Broker MQTT: {self.broker_host}:{self.broker_port}")
        print(f"Tópico: {TOPIC_SUBSCRIBE}")
        print(f"API REST: http://{self.api_host}:{self.api_port}")
        print(f"Arquivo CSV: {self.arquivo_csv}")
        print("=" * 70)
        
        # Inicia API REST
        self._iniciar_api()
        
        if self.conectar():
            try:
                print("\n[INFO] Backend ativo. Pressione Ctrl+C para parar.\n")
                # Mantém o programa rodando
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n[INFO] Encerrando servidor...")
                print(f"[ESTATÍSTICAS] Leituras recebidas: {self.leituras_recebidas}")
                print(f"[ESTATÍSTICAS] Alertas recebidos: {self.alertas_recebidos}")
                print(f"[INFO] Dados salvos em: {self.arquivo_csv}")
                self.client.loop_stop()
                self.client.disconnect()
                print("[INFO] Servidor encerrado.")
        else:
            print("[ERRO] Não foi possível iniciar o servidor.")


def main():
    parser = argparse.ArgumentParser(
        description="Servidor backend que recebe dados MQTT e expõe API REST"
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
        help=f"Host da API REST (padrão: {API_HOST})"
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=API_PORT,
        help=f"Porta da API REST (padrão: {API_PORT})"
    )
    
    args = parser.parse_args()
    
    servidor = ServidorBackend(
        broker_host=args.broker,
        broker_port=args.port,
        arquivo_csv=args.csv,
        api_host=args.api_host,
        api_port=args.api_port
    )
    
    servidor.executar()


if __name__ == "__main__":
    main()
