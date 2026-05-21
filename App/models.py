from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    pokemon = db.relationship('UserPokemon', back_populates='trainer', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {'id': self.id, 'username': self.username}


class Pokemon(db.Model):
    __tablename__ = 'pokemon'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    attack = db.Column(db.Integer, nullable=True)
    defense = db.Column(db.Integer, nullable=True)
    hp = db.Column(db.Integer, nullable=True)
    sp_attack = db.Column(db.Integer, nullable=True)
    sp_defense = db.Column(db.Integer, nullable=True)
    speed = db.Column(db.Integer, nullable=True)
    type1 = db.Column(db.String(50), nullable=False)
    type2 = db.Column(db.String(50), nullable=True)
    trainer = db.relationship('UserPokemon', back_populates='pokemon', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type1': self.type1,
            'type2': self.type2,
            'hp': self.hp,
            'attack': self.attack,
            'defense': self.defense,
            'sp_attack': self.sp_attack,
            'sp_defense': self.sp_defense,
            'speed': self.speed,
        }


class UserPokemon(db.Model):
    __tablename__ = 'user_pokemon'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pokemon_id = db.Column(db.Integer, db.ForeignKey('pokemon.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    trainer = db.relationship('User', back_populates='pokemon')
    pokemon = db.relationship('Pokemon', back_populates='trainer')

    def to_dict(self):
        return {
            'id': self.id,
            'pokemon_id': self.pokemon_id,
            'name': self.name,
            'type1': self.pokemon.type1 if self.pokemon else None,
            'type2': self.pokemon.type2 if self.pokemon else None,
        }


