"""
Script para inicializar o banco de dados
"""
import os
from dotenv import load_dotenv
from src.models import db, init_db
from src.config import DATABASE_URL
from flask import Flask

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', DATABASE_URL)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

if __name__ == "__main__":
    print("Inicializando banco de dados...")
    with app.app_context():
        init_db(app)
        print("✅ Banco de dados inicializado com sucesso!")

