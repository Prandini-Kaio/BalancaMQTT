import paho.mqtt.client as mqtt
import time
import random
import json
import argparse
from threading import Thread

# Config padrão
BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883
TOPIC_BASE = "estoque"
PESO_INICIAL_MIN = 5000  # gramas
PESO_INICIAL_MAX = 10000  # gramas
PESO_CRITICO_PERCENTUAL = 0.2  # 20% do peso inicil
INTERVALO_MEDICAO = 3  # segundos


"""
Sistema de Simulação de Sensores de Peso --- Publicador MQTT ---
Simula sensores de peso em prateleiras que publicam leituras via MQTT
"""

class SensorPeso:
    """Essa classe que representa um sensor de peso em uma prateleira"""
    
    def __init__(self, prateleira_id, sensor_id, peso_inicial, peso_critico, client):
        self.prateleira_id = prateleira_id
        self.sensor_id = sensor_id
        self.peso_atual = peso_inicial
        self.peso_inicial = peso_inicial
        self.peso_critico = peso_critico
        self.client = client
        self.topic_peso = f"{TOPIC_BASE}/prateleira{prateleira_id}/sensor{sensor_id}/peso"
        self.topic_alerta = f"{TOPIC_BASE}/prateleira{prateleira_id}/sensor{sensor_id}/alerta"
        self.ativo = False
    
    def simular_retirada(self):
        """Simula a retirada de produtos (reduz peso alatoriamente)"""
        # Reduz entre 5% e 15% do peso atual, mas não deixa ficar negativo
        reducao_percentual = random.uniform(0.05, 0.15)
        reducao = self.peso_atual * reducao_percentual
        self.peso_atual = max(0, self.peso_atual - reducao)
        
        # Pode haver reposição (aumentar peso)
        if random.random() < 0.1:
            reposicao = random.uniform(100, 500)
            self.peso_atual = min(self.peso_inicial, self.peso_atual + reposicao)
    
    def verificar_alerta(self):
        """Verifica se o peso ta abaixo do nível critico"""
        return self.peso_atual <= self.peso_critico
    
    def publicar_medicao(self):
        """Publica a leitura atual de peso via MQTT"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        percentual_restante = (self.peso_atual / self.peso_inicial) * 100
        
        dados = {
            "prateleira_id": self.prateleira_id,
            "sensor_id": self.sensor_id,
            "peso_gramas": round(self.peso_atual, 2),
            "peso_inicial": self.peso_inicial,
            "percentual_restante": round(percentual_restante, 2),
            "timestamp": timestamp
        }
        
        # Publica a leitura de peso
        mensagem = json.dumps(dados, ensure_ascii=False)
        result = self.client.publish(self.topic_peso, mensagem, qos=1)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[PUBLICADOR] Prateleira {self.prateleira_id} - Sensor {self.sensor_id}: "
                  f"{self.peso_atual:.2f}g ({percentual_restante:.1f}% restante) | Tópico: {self.topic_peso}")
        else:
            print(f"[ERRO] Falha ao publicar. Código: {result.rc}")
        
        # Verifica e publica alerta se necessário
        if self.verificar_alerta():
            alerta = {
                "prateleira_id": self.prateleira_id,
                "sensor_id": self.sensor_id,
                "peso_atual": round(self.peso_atual, 2),
                "peso_critico": self.peso_critico,
                "tipo": "REPOSICAO_URGENTE",
                "mensagem": f"⚠️ PESO CRÍTICO! Reposição necessária na Prateleira {self.prateleira_id}, Sensor {self.sensor_id}",
                "timestamp": timestamp
            }
            mensagem_alerta = json.dumps(alerta, ensure_ascii=False)
            result = self.client.publish(self.topic_alerta, mensagem_alerta, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[⚠️ ALERTA] {alerta['mensagem']} | Tópico: {self.topic_alerta}")
            else:
                print(f"[ERRO] Falha ao publicar alerta. Código: {result.rc}")
    
    def executar(self):
        """Loop principal do sensor, vai executae as medições periodicamente"""
        self.ativo = True
        print(f"[INICIADO] Sensor {self.sensor_id} da Prateleira {self.prateleira_id} "
              f"(Peso inicial: {self.peso_inicial:.2f}g, Crítico: {self.peso_critico:.2f}g)")
        
        while self.ativo:
            self.simular_retirada()
            self.publicar_medicao()
            time.sleep(INTERVALO_MEDICAO)
    
    def parar(self):
        """Para a execução do sensor"""
        self.ativo = False


class PublicadorBalancas:
    """Classe principal que gerencia múltiplos sensores de peso"""
    
    def __init__(self, broker_host, broker_port, prateleiras_config):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.prateleiras_config = prateleiras_config
        self.client = mqtt.Client(client_id="publicador_balancas")
        self.sensores = []
        self.threads = []
        self.conectado = False
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback quando conecta ao broker"""
        if rc == 0:
            self.conectado = True
            print(f"[CONECTADO] Broker MQTT: {self.broker_host}:{self.broker_port}")
        else:
            self.conectado = False
            print(f"[ERRO] Falha na conexão. Código: {rc}")
    
    def on_publish(self, client, userdata, mid):
        """Callback quando publica uma mensagem"""

        # Usado somente para LOG, mas deixado o metodo caso precise
        print(f"[PUBLICADO] Mensagem publicada (mid: {mid})")
        pass
    
    def conectar(self):
        """Conecta ao broker MQTT"""
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            # Aguarda conexão estabelecer max 5 segundos
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
    
    def criar_sensores(self):
        """Cria sensores baseado na configuração das prateleiras"""
        for prateleira_id, num_sensores in self.prateleiras_config.items():
            for sensor_id in range(1, num_sensores + 1):
                peso_inicial = random.uniform(PESO_INICIAL_MIN, PESO_INICIAL_MAX)
                peso_critico = peso_inicial * PESO_CRITICO_PERCENTUAL
                
                sensor = SensorPeso(
                    prateleira_id=prateleira_id,
                    sensor_id=sensor_id,
                    peso_inicial=peso_inicial,
                    peso_critico=peso_critico,
                    client=self.client
                )
                self.sensores.append(sensor)
    
    def iniciar(self):
        """Inicia todos os sensores em threads separadas :D"""
        if not self.conectar():
            return False
        
        self.criar_sensores()
        
        print(f"\n[INFO] Iniciando {len(self.sensores)} sensores...")
        print("=" * 70)
        
        for sensor in self.sensores:
            thread = Thread(target=sensor.executar, daemon=True)
            thread.start()
            self.threads.append(thread)
        
        return True
    
    def executar(self):
        """Executa o publicador"""
        if self.iniciar():
            try:
                print("\n[INFO] Publicador ativo. Pressione Ctrl+C para parar.\n")
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n[INFO] Parando publicadores...")
                for sensor in self.sensores:
                    sensor.parar()
                self.client.loop_stop()
                self.client.disconnect()
                print("[INFO] Publicador encerrado.")
        else:
            print("[ERRO] Não foi possível iniciar o publicador.")


def main():
    parser = argparse.ArgumentParser(
        description="Simula sensores de peso que publicam dados via MQTT"
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
        "--prateleiras",
        default="1:1,2:2,3:1",
        help="Configuração de prateleiras no formato 'id:num_sensores,id:num_sensores' "
             "(ex: '1:1,2:2,3:1' = Prateleira 1 com 1 sensor, Prateleira 2 com 2 sensores, etc.)"
    )
    
    args = parser.parse_args()
    
    # Parse da configuração de prateleiras
    prateleiras_config = {}
    try:
        for item in args.prateleiras.split(','):
            prateleira_id, num_sensores = item.split(':')
            prateleiras_config[int(prateleira_id)] = int(num_sensores)
    except ValueError:
        print("[ERRO] Formato inválido para --prateleiras. Use: '1:1,2:2,3:1'")
        return
    
    print("=" * 70)
    print("SISTEMA DE SIMULAÇÃO DE SENSORES DE PESO - PUBLICADOR MQTT")
    print("=" * 70)
    print(f"Broker: {args.broker}:{args.port}")
    print(f"Configuração: {prateleiras_config}")
    print("=" * 70)
    
    publicador = PublicadorBalancas(
        broker_host=args.broker,
        broker_port=args.port,
        prateleiras_config=prateleiras_config
    )
    
    publicador.executar()


if __name__ == "__main__":
    main()
