"""
Script para criar um usuário administrador inicial
"""
import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.models import db, User, init_db
from src.config import DATABASE_URL
from flask import Flask

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', DATABASE_URL)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def criar_admin():
    """Cria um usuário administrador"""
    with app.app_context():
        # Inicializa banco se necessário
        init_db(app)
        
        # Verifica se já existe admin
        admin_existente = User.query.filter_by(admin=True).first()
        if admin_existente:
            print(f"[INFO] Já existe um administrador: {admin_existente.username}")
            resposta = input("Deseja criar outro administrador? (s/n): ")
            if resposta.lower() != 's':
                return
        
        # Solicita dados
        username = input("Username: ").strip()
        if not username:
            print("[ERRO] Username não pode ser vazio")
            return
        
        email = input("Email: ").strip()
        if not email:
            print("[ERRO] Email não pode ser vazio")
            return
        
        password = input("Senha (mínimo 6 caracteres): ").strip()
        if len(password) < 6:
            print("[ERRO] Senha deve ter pelo menos 6 caracteres")
            return
        
        # Verifica se usuário já existe
        if User.query.filter_by(username=username).first():
            print(f"[ERRO] Usuário '{username}' já existe")
            return
        
        if User.query.filter_by(email=email).first():
            print(f"[ERRO] Email '{email}' já está cadastrado")
            return
        
        # Cria usuário admin
        admin = User(
            username=username,
            email=email,
            admin=True,
            ativo=True
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        print(f"\n Administrador criado com sucesso!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Admin: Sim")

if __name__ == "__main__":
    print("=" * 60)
    print("CRIAR USUÁRIO ADMINISTRADOR")
    print("=" * 60)
    criar_admin()


