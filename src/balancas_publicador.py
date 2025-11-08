import paho.mqtt.client as mqtt
import time
import random
import json
import argparse
import requests
from threading import Thread, Lock
from flask import Flask, jsonify, request
from flask_cors import CORS

# Config padrão
BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883
TOPIC_BASE = "estoque"
API_URL = "http://localhost:5000"
INTERVALO_MEDICAO = 3  # segundos
INTERVALO_VERIFICACAO_PRODUTOS = 10  # segundos - intervalo para verificar novos produtos
API_PORT_PUBLICADOR = 5001  # Porta para API do publicador


"""
Sistema de Simulação de Sensores de Peso - Publicador MQTT
Simula sensores de peso associados a produtos cadastrados via API
Cada sensor representa um produto único
"""

class SensorPeso:
    """Representa um sensor de peso associado a um produto"""
    
    def __init__(self, produto_id, produto_nome, peso_inicial, peso_minimo, peso_maximo, peso_ideal, topic, client):
        self.produto_id = produto_id
        self.produto_nome = produto_nome
        self.peso_atual = peso_inicial
        self.peso_inicial = peso_inicial
        self.peso_minimo = peso_minimo
        self.peso_maximo = peso_maximo
        self.peso_ideal = peso_ideal
        self.peso_critico = peso_minimo  # Peso crítico = peso mínimo
        self.topic = topic
        self.client = client
        self.topic_peso = topic
        # Tópico de alerta: substitui /peso por /alerta ou adiciona /alerta no final
        if topic.endswith('/peso'):
            self.topic_alerta = topic.replace('/peso', '/alerta')
        else:
            self.topic_alerta = f"{topic}/alerta"
        self.ativo = False
    
    def simular_retirada(self):
        """Simula a retirada de produtos (reduz peso aleatoriamente)"""

        # Reduz entre 5% e 15% do peso atual, mas não deixa ficar negativo
        reducao_percentual = random.uniform(0.05, 0.15)
        reducao = self.peso_atual * reducao_percentual
        self.peso_atual = max(0, self.peso_atual - reducao)
        
        # Ocasionalmente pode haver reposição (aumenta peso até o máximo)
        if random.random() < 0.1:  # 10% de chance de reposição
            reposicao = random.uniform(1000, 5000)  # Entre 1kg e 5kg
            self.peso_atual = min(self.peso_maximo * 1000, self.peso_atual + reposicao)
    
    def verificar_alerta(self):
        """Verifica se o peso está abaixo do nível crítico"""
        return self.peso_atual <= (self.peso_critico * 1000)  # Converte para gramas
    
    def publicar_medicao(self):
        """Publica a leitura atual de peso via MQTT"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        percentual_restante = (self.peso_atual / (self.peso_maximo * 1000)) * 100
        
        dados = {
            "produto_id": self.produto_id,
            "produto_nome": self.produto_nome,
            "peso_gramas": round(self.peso_atual, 2),
            "peso_inicial": self.peso_inicial,
            "percentual_restante": round(percentual_restante, 2),
            "timestamp": timestamp
        }
        
        # Publica a leitura de peso
        mensagem = json.dumps(dados, ensure_ascii=False)
        result = self.client.publish(self.topic_peso, mensagem, qos=1)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[PUBLICADOR] {self.produto_nome}: {self.peso_atual/1000:.2f}kg ({percentual_restante:.1f}% restante)")
        else:
            print(f"[ERRO] Falha ao publicar. Código: {result.rc}")
        
        # Verifica e publica alerta se necessário
        if self.verificar_alerta():
            alerta = {
                "produto_id": self.produto_id,
                "produto_nome": self.produto_nome,
                "peso_atual": round(self.peso_atual, 2),
                "peso_critico": self.peso_critico * 1000,  # Converte para gramas
                "tipo": "REPOSICAO_URGENTE",
                "mensagem": f"⚠️ PESO CRÍTICO! Reposição necessária para {self.produto_nome}",
                "timestamp": timestamp
            }
            mensagem_alerta = json.dumps(alerta, ensure_ascii=False)
            result = self.client.publish(self.topic_alerta, mensagem_alerta, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[⚠️ ALERTA] {alerta['mensagem']}")
            else:
                print(f"[ERRO] Falha ao publicar alerta. Código: {result.rc}")
    
    def executar(self):
        """Loop principal do sensor - executa medições periodicamente"""
        self.ativo = True
        print(f"[INICIADO] {self.produto_nome} - Produto ID {self.produto_id} "
              f"(Peso inicial: {self.peso_atual/1000:.2f}kg, Min: {self.peso_minimo}kg, Max: {self.peso_maximo}kg)")
        
        while self.ativo:
            self.simular_retirada()
            self.publicar_medicao()
            time.sleep(INTERVALO_MEDICAO)
    
    def parar(self):
        """Para a execução do sensor"""
        self.ativo = False
    
    def retirar_peso(self, quantidade_kg):
        """Retira peso do produto manualmente"""
        quantidade_gramas = quantidade_kg * 1000
        self.peso_atual = max(0, self.peso_atual - quantidade_gramas)
        print(f"[RETIRADA MANUAL] {self.produto_nome}: {quantidade_kg:.2f}kg retirados. Novo peso: {self.peso_atual/1000:.2f}kg")
        return self.peso_atual / 1000  # Retorna peso em KG
    
    def repor_peso(self, quantidade_kg):
        """Repõe peso do produto manualmente"""
        quantidade_gramas = quantidade_kg * 1000
        self.peso_atual = min(self.peso_maximo * 1000, self.peso_atual + quantidade_gramas)
        print(f"[REPOSIÇÃO MANUAL] {self.produto_nome}: {quantidade_kg:.2f}kg adicionados. Novo peso: {self.peso_atual/1000:.2f}kg")
        return self.peso_atual / 1000  # Retorna peso em KG
    
    def get_status(self):
        """Retorna status atual do sensor"""
        return {
            'produto_id': self.produto_id,
            'produto_nome': self.produto_nome,
            'peso_atual_kg': round(self.peso_atual / 1000, 2),
            'peso_minimo_kg': self.peso_minimo,
            'peso_maximo_kg': self.peso_maximo,
            'peso_ideal_kg': self.peso_ideal,
            'ativo': self.ativo,
            'percentual_restante': round((self.peso_atual / (self.peso_maximo * 1000)) * 100, 2)
        }


class PublicadorBalancas:
    """Classe principal que gerencia múltiplos sensores de peso (produtos)"""
    
    def __init__(self, broker_host, broker_port, api_url, api_port_publicador):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.api_url = api_url
        self.api_port_publicador = api_port_publicador
        self.client = mqtt.Client(client_id="publicador_balancas")
        self.sensores = []
        self.threads = []
        self.conectado = False
        self.lock = Lock()
        self.produtos_processados = set()  # IDs de produtos já processados
        self.running = False
        
        # Flask app para API REST do publicador
        self.app = Flask(__name__)
        CORS(self.app)
        self._configurar_rotas_api()
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback quando conecta ao broker"""
        if rc == 0:
            self.conectado = True
            print(f"[CONECTADO] Broker MQTT: {self.broker_host}:{self.broker_port}")
        else:
            self.conectado = False
            print(f"[ERRO] Falha na conexão. Código: {rc}")
    
    def conectar(self):
        """Conecta ao broker MQTT"""
        self.client.on_connect = self.on_connect
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            # Aguarda conexão estabelecer (até 5 segundos)
            for i in range(10):
                if self.conectado:
                    break
                time.sleep(0.5)
            
            if not self.conectado:
                print("[ERRO] Timeout ao conectar ao broker")
                return False
        except Exception as e:
            print(f"[ERRO] Não foi possível conectar ao broker: {e}")
            print(f"[INFO] Certifique-se de que um broker MQTT está rodando em {self.broker_host}:{self.broker_port}")
            return False
        return True
    
    def obter_produtos_cadastrados(self):
        """Obtém produtos cadastrados via API"""
        try:
            response = requests.get(f"{self.api_url}/api/produtos", timeout=5)
            if response.status_code == 200:
                produtos = response.json()
                print(f"[INFO] {len(produtos)} produto(s) encontrado(s) via API")
                return produtos
            else:
                print(f"[ERRO] Falha ao obter produtos. Status: {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"[ERRO] Não foi possível conectar à API: {e}")
            print(f"[INFO] Certifique-se de que o servidor backend está rodando em {self.api_url}")
            return []
    
    def criar_sensores(self, produtos):
        """Cria sensores baseado nos produtos cadastrados"""
        if not produtos:
            return 0
        
        novos_sensores = 0
        with self.lock:
            for produto in produtos:
                produto_id = produto['produto_id']
                
                # Verifica se o produto já foi processado
                if produto_id in self.produtos_processados:
                    continue
                
                produto_nome = produto['nome']
                peso_minimo = produto['pesoMinimo']
                peso_maximo = produto['pesoMaximo']
                peso_ideal = produto.get('pesoIdeal', peso_minimo * 2)
                topic = produto.get('topic', f"{TOPIC_BASE}/produto{produto_id}/peso")
                
                # Peso inicial aleatório entre peso ideal e peso máximo
                peso_inicial_kg = random.uniform(peso_ideal, peso_maximo)
                peso_inicial_gramas = peso_inicial_kg * 1000
                
                sensor = SensorPeso(
                    produto_id=produto_id,
                    produto_nome=produto_nome,
                    peso_inicial=peso_inicial_gramas,
                    peso_minimo=peso_minimo,
                    peso_maximo=peso_maximo,
                    peso_ideal=peso_ideal,
                    topic=topic,
                    client=self.client
                )
                self.sensores.append(sensor)
                self.produtos_processados.add(produto_id)
                novos_sensores += 1
        
        return novos_sensores
    
    def _verificar_novos_produtos(self):
        """Thread que verifica periodicamente novos produtos cadastrados"""
        while self.running:
            try:
                produtos = self.obter_produtos_cadastrados()
                if produtos:
                    novos_sensores = self.criar_sensores(produtos)
                    if novos_sensores > 0:
                        print(f"[INFO] {novos_sensores} novo(s) produto(s) encontrado(s). Iniciando sensores...")
                        # Inicia novos sensores
                        with self.lock:
                            sensores_para_iniciar = [s for s in self.sensores if not s.ativo]
                            for sensor in sensores_para_iniciar:
                                thread = Thread(target=sensor.executar, daemon=True)
                                thread.start()
                                self.threads.append(thread)
            except Exception as e:
                print(f"[ERRO] Erro ao verificar novos produtos: {e}")
            
            # Aguarda antes de verificar novamente
            time.sleep(INTERVALO_VERIFICACAO_PRODUTOS)
    
    def _configurar_rotas_api(self):
        """Configura rotas da API REST do publicador"""
        
        @self.app.route('/api/ping', methods=['GET'])
        def ping():
            return jsonify({'status': 'ok', 'message': 'pong'})
        
        @self.app.route('/api/sensores', methods=['GET'])
        def listar_sensores():
            """Lista todos os sensores ativos"""
            with self.lock:
                sensores_status = [sensor.get_status() for sensor in self.sensores]
            return jsonify(sensores_status)
        
        @self.app.route('/api/sensores/<int:produto_id>/retirada', methods=['POST'])
        def retirar_peso(produto_id):
            """Retira peso de um sensor específico"""
            try:
                data = request.get_json() or {}
                quantidade_kg = float(data.get('quantidade', 0))
                
                with self.lock:
                    sensor = next((s for s in self.sensores if s.produto_id == produto_id), None)
                    if not sensor:
                        return jsonify({'erro': 'Sensor não encontrado'}), 404
                    
                    if quantidade_kg <= 0:
                        quantidade_kg = (sensor.peso_atual / 1000) * random.uniform(0.05, 0.15)
                    
                    peso_novo = sensor.retirar_peso(quantidade_kg)
                    
                return jsonify({
                    'mensagem': 'Peso retirado com sucesso',
                    'produto_id': produto_id,
                    'produto_nome': sensor.produto_nome,
                    'quantidade_retirada': round(quantidade_kg, 2),
                    'peso_novo': round(peso_novo, 2)
                }), 200
            except ValueError as e:
                return jsonify({'erro': f'Valor inválido: {str(e)}'}), 400
            except Exception as e:
                return jsonify({'erro': f'Erro ao retirar peso: {str(e)}'}), 500
        
        @self.app.route('/api/sensores/<int:produto_id>/reposicao', methods=['POST'])
        def repor_peso(produto_id):
            """Repõe peso de um sensor específico"""
            try:
                data = request.get_json() or {}
                quantidade_kg = float(data.get('quantidade', 0))
                
                with self.lock:
                    sensor = next((s for s in self.sensores if s.produto_id == produto_id), None)
                    if not sensor:
                        return jsonify({'erro': 'Sensor não encontrado'}), 404
                    
                    if quantidade_kg <= 0:
                        quantidade_kg = random.uniform(1, 5)
                    
                    peso_novo = sensor.repor_peso(quantidade_kg)
                    
                return jsonify({
                    'mensagem': 'Peso reposto com sucesso',
                    'produto_id': produto_id,
                    'produto_nome': sensor.produto_nome,
                    'quantidade_adicionada': round(quantidade_kg, 2),
                    'peso_novo': round(peso_novo, 2)
                }), 200
            except ValueError as e:
                return jsonify({'erro': f'Valor inválido: {str(e)}'}), 400
            except Exception as e:
                return jsonify({'erro': f'Erro ao repor peso: {str(e)}'}), 500
        
        @self.app.route('/api/sensores/<int:produto_id>', methods=['GET'])
        def status_sensor(produto_id):
            """Retorna status de um sensor específico"""
            with self.lock:
                sensor = next((s for s in self.sensores if s.produto_id == produto_id), None)
                if not sensor:
                    return jsonify({'erro': 'Sensor não encontrado'}), 404
                return jsonify(sensor.get_status()), 200
    
    def _iniciar_api(self):
        """Inicia o servidor Flask da API REST em thread separada"""
        def run_api():
            self.app.run(host='0.0.0.0', port=self.api_port_publicador, debug=False, use_reloader=False)
        
        thread = Thread(target=run_api, daemon=True)
        thread.start()
        time.sleep(1)  # Aguarda servidor iniciar
        print(f"[API] API REST do publicador iniciada em http://0.0.0.0:{self.api_port_publicador}")
        print(f"[API] Endpoints disponíveis:")
        print(f"       GET  /api/ping - Status")
        print(f"       GET  /api/sensores - Listar sensores")
        print(f"       GET  /api/sensores/<id> - Status de um sensor")
        print(f"       POST /api/sensores/<id>/retirada - Retirar peso")
        print(f"       POST /api/sensores/<id>/reposicao - Repor peso")
    
    def iniciar(self):
        """Inicia todos os sensores em threads separadas"""
        if not self.conectar():
            return False
        
        # Inicia API REST do publicador
        self._iniciar_api()
        
        # Obtém produtos cadastrados via API
        produtos = self.obter_produtos_cadastrados()
        if not produtos:
            print("[AVISO] Nenhum produto cadastrado. O publicador verificará novos produtos periodicamente.")
        else:
            novos_sensores = self.criar_sensores(produtos)
            if novos_sensores > 0:
                print(f"\n[INFO] Iniciando {novos_sensores} sensor(es)...")
                print("=" * 70)
                
                with self.lock:
                    for sensor in self.sensores:
                        if not sensor.ativo:
                            thread = Thread(target=sensor.executar, daemon=True)
                            thread.start()
                            self.threads.append(thread)
        
        # Inicia thread para verificar novos produtos periodicamente
        self.running = True
        thread_verificacao = Thread(target=self._verificar_novos_produtos, daemon=True)
        thread_verificacao.start()
        
        return True
    
    def executar(self):
        """Executa o publicador"""
        if self.iniciar():
            try:
                print("\n[INFO] Publicador ativo. Pressione Ctrl+C para parar.")
                print(f"[INFO] Verificando novos produtos a cada {INTERVALO_VERIFICACAO_PRODUTOS} segundos.\n")
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n[INFO] Parando publicadores...")
                self.running = False
                with self.lock:
                    for sensor in self.sensores:
                        sensor.parar()
                self.client.loop_stop()
                self.client.disconnect()
                print("[INFO] Publicador encerrado.")
        else:
            print("[ERRO] Não foi possível iniciar o publicador.")


def main():
    parser = argparse.ArgumentParser(
        description="Simula sensores de peso associados a produtos cadastrados via API"
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
        "--api-url",
        default=API_URL,
        help=f"URL da API backend (padrão: {API_URL})"
    )
    parser.add_argument(
        "--api-port-publicador",
        type=int,
        default=API_PORT_PUBLICADOR,
        help=f"Porta da API REST do publicador (padrão: {API_PORT_PUBLICADOR})"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("SISTEMA DE SIMULAÇÃO DE SENSORES DE PESO - PUBLICADOR MQTT")
    print("=" * 70)
    print(f"Broker: {args.broker}:{args.port}")
    print(f"API Backend: {args.api_url}")
    print(f"API Publicador: http://0.0.0.0:{args.api_port_publicador}")
    print("=" * 70)
    
    publicador = PublicadorBalancas(
        broker_host=args.broker,
        broker_port=args.port,
        api_url=args.api_url,
        api_port_publicador=args.api_port_publicador
    )
    
    publicador.executar()


if __name__ == "__main__":
    main()