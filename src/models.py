"""
Modelos de banco de dados para o sistema de controle de estoque por peso
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Produto(db.Model):
    """Modelo para produtos cadastrados"""
    __tablename__ = 'produtos'
    
    produto_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    peso_minimo = db.Column(db.Float, nullable=False)  # KG
    peso_maximo = db.Column(db.Float, nullable=False)  # KG
    peso_ideal = db.Column(db.Float, nullable=False)  # KG
    topic = db.Column(db.String(200), nullable=False, unique=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    leituras = db.relationship('Leitura', backref='produto', lazy=True, cascade='all, delete-orphan')
    alertas = db.relationship('Alerta', backref='produto', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'produto_id': self.produto_id,
            'nome': self.nome,
            'pesoMinimo': self.peso_minimo,
            'pesoMaximo': self.peso_maximo,
            'pesoIdeal': self.peso_ideal,
            'topic': self.topic,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None
        }
    
    def __repr__(self):
        return f"<Produto {self.produto_id}: {self.nome}>"


class Leitura(db.Model):
    """Modelo para leituras de peso recebidas dos sensores"""
    __tablename__ = 'leituras'
    
    leitura_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.produto_id'), nullable=False)
    peso_gramas = db.Column(db.Float, nullable=False)
    peso_kg = db.Column(db.Float, nullable=False)  # Calculado para facilitar consultas
    peso_inicial = db.Column(db.Float)  # Peso inicial em gramas
    percentual_restante = db.Column(db.Float)
    timestamp_sensor = db.Column(db.DateTime)  # Timestamp do sensor
    timestamp_recebimento = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'leitura_id': self.leitura_id,
            'produto_id': self.produto_id,
            'peso_gramas': self.peso_gramas,
            'peso_kg': self.peso_kg,
            'peso_inicial': self.peso_inicial,
            'percentual_restante': self.percentual_restante,
            'timestamp_sensor': self.timestamp_sensor.isoformat() if self.timestamp_sensor else None,
            'timestamp_recebimento': self.timestamp_recebimento.isoformat() if self.timestamp_recebimento else None
        }
    
    def __repr__(self):
        return f"<Leitura {self.leitura_id}: Produto {self.produto_id} - {self.peso_kg}kg>"


class Alerta(db.Model):
    """Modelo para alertas de reposição"""
    __tablename__ = 'alertas'
    
    alerta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.produto_id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False, default='REPOSICAO_URGENTE')
    mensagem = db.Column(db.String(500), nullable=False)
    peso_atual_kg = db.Column(db.Float, nullable=False)
    peso_critico_kg = db.Column(db.Float, nullable=False)
    timestamp_sensor = db.Column(db.DateTime)  # Timestamp do sensor
    timestamp_recebimento = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolvido = db.Column(db.Boolean, default=False, nullable=False)
    resolvido_em = db.Column(db.DateTime)
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'alerta_id': self.alerta_id,
            'produto_id': self.produto_id,
            'tipo': self.tipo,
            'mensagem': self.mensagem,
            'peso_atual_kg': self.peso_atual_kg,
            'peso_critico_kg': self.peso_critico_kg,
            'timestamp_sensor': self.timestamp_sensor.isoformat() if self.timestamp_sensor else None,
            'timestamp_recebimento': self.timestamp_recebimento.isoformat() if self.timestamp_recebimento else None,
            'resolvido': self.resolvido,
            'resolvido_em': self.resolvido_em.isoformat() if self.resolvido_em else None
        }
    
    def __repr__(self):
        return f"<Alerta {self.alerta_id}: Produto {self.produto_id} - {self.tipo}>"


def init_db(app):
    """Inicializa o banco de dados"""
    import time
    max_retries = 10
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            with app.app_context():
                db.create_all()
                print("[DB] ✅ Tabelas criadas/verificadas com sucesso")
                return
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[DB] ⚠️ Tentativa {attempt + 1}/{max_retries} - Aguardando banco de dados... ({str(e)})")
                time.sleep(retry_delay)
            else:
                print(f"[DB] ❌ ERRO: Não foi possível conectar ao banco de dados após {max_retries} tentativas")
                print(f"[DB] Erro: {str(e)}")
                raise

