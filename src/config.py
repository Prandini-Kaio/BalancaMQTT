"""
Configurações do sistema
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://balanca:balanca123@postgres:5432/balancas_db')

# MQTT
BROKER_HOST = os.getenv('BROKER_HOST', 'test.mosquitto.org')
BROKER_PORT = int(os.getenv('BROKER_PORT', '1883'))
TOPIC_BASE = os.getenv('TOPIC_BASE', 'estoque')

# API
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '5000'))
PUBLICADOR_API_URL = os.getenv('PUBLICADOR_API_URL', 'http://publicador:5001')

# CSV (backup)
ARQUIVO_CSV = os.getenv('ARQUIVO_CSV', 'dados.csv')

# JWT
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'sua-chave-secreta-mude-em-producao-12345')
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '86400'))  # 24 horas em segundos

