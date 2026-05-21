import os
import csv
import click
from flask import Flask, request, jsonify, render_template
from flask.cli import with_appcontext
from flask_cors import CORS
from sqlalchemy.exc import IntegrityError
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)

from .models import db, User, Pokemon, UserPokemon

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder='../templates', static_folder='../static')

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(_BASE_DIR, 'instance', 'data.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-dev-secret')
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']
app.config['JWT_COOKIE_SECURE'] = False
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_HEADER_NAME'] = 'Authorization'
app.config['JWT_HEADER_TYPE'] = 'Bearer'

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------
db.init_app(app)
CORS(app)
jwt = JWTManager(app)

# ---------------------------------------------------------------------------
# CLI: flask init
# ---------------------------------------------------------------------------
@click.command('init', help='Drop, recreate, and seed the database from pokemon.csv')
@with_appcontext
def initialize_db():
    db.drop_all()
    db.create_all()

    csv_path = os.path.join(os.path.dirname(__file__), '..', 'pokemon.csv')
    count = 0
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            p = Pokemon(
                id=i,
                name=row.get('name', '').strip(),
                hp=_int(row.get('hp')),
                attack=_int(row.get('attack')),
                defense=_int(row.get('defense')),
                sp_attack=_int(row.get('sp_attack')),
                sp_defense=_int(row.get('sp_defense')),
                speed=_int(row.get('speed')),
                type1=row.get('type1', '').strip(),
                type2=row.get('type2', '').strip() or None,
            )
            db.session.add(p)
            count += 1
    db.session.commit()
    click.echo(f'Database initialized with {count} Pokemon.')

app.cli.add_command(initialize_db)


def _int(val):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None

# ---------------------------------------------------------------------------
# Routes — Frontend
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'username and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': f'User {username} created successfully'}), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password'}), 401

    token = create_access_token(identity=str(user.id))
    response = jsonify({'token': token, 'user': user.to_dict()})
    set_access_cookies(response, token)
    return response, 200


@app.route('/logout', methods=['GET'])
def logout():
    response = jsonify({'message': 'Logged out successfully'})
    unset_jwt_cookies(response)
    return response, 200


# ---------------------------------------------------------------------------
# Routes — Pokemon Directory
# ---------------------------------------------------------------------------
@app.route('/pokemon/', methods=['GET'])
def list_pokemon():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    q = request.args.get('q', '').strip()

    query = Pokemon.query
    if q:
        query = query.filter(Pokemon.name.ilike(f'%{q}%'))

    pagination = query.order_by(Pokemon.id).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
        'per_page': pagination.per_page,
        'pokemon': [p.to_dict() for p in pagination.items],
    }), 200


@app.route('/pokemon/<int:pokemon_id>', methods=['GET'])
def get_pokemon(pokemon_id):
    p = Pokemon.query.get(pokemon_id)
    if not p:
        return jsonify({'error': f'Pokemon {pokemon_id} not found'}), 404
    return jsonify(p.to_dict()), 200


# ---------------------------------------------------------------------------
# Routes — My Pokemon (JWT protected)
# ---------------------------------------------------------------------------
@app.route('/mypokemon/', methods=['GET'])
@jwt_required()
def get_my_pokemon():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify([up.to_dict() for up in user.pokemon]), 200


@app.route('/mypokemon/', methods=['POST'])
@jwt_required()
def catch_pokemon():
    data = request.get_json(silent=True) or {}
    user_id = int(get_jwt_identity())
    pokemon_id = data.get('pokemon_id')
    name = (data.get('name') or '').strip()

    if not pokemon_id:
        return jsonify({'error': 'pokemon_id is required'}), 400

    pokemon = Pokemon.query.get(pokemon_id)
    if not pokemon:
        return jsonify({'error': f'Pokemon {pokemon_id} not found'}), 404

    nickname = name if name else pokemon.name
    user_pokemon = UserPokemon(user_id=user_id, pokemon_id=pokemon_id, name=nickname)
    db.session.add(user_pokemon)
    db.session.commit()
    return jsonify({'message': f'{nickname} caught!', 'user_pokemon': user_pokemon.to_dict()}), 201


@app.route('/mypokemon/', methods=['PUT'])
@jwt_required()
def update_pokemon():
    data = request.get_json(silent=True) or {}
    user_id = int(get_jwt_identity())
    up_id = data.get('id')
    new_name = (data.get('name') or '').strip()

    if not up_id or not new_name:
        return jsonify({'error': 'id and name are required'}), 400

    user_pokemon = UserPokemon.query.filter_by(id=up_id, user_id=user_id).first()
    if not user_pokemon:
        return jsonify({'error': f'Entry {up_id} not found or does not belong to you'}), 404

    user_pokemon.name = new_name
    db.session.commit()
    return jsonify({'message': f'Renamed to {new_name}', 'user_pokemon': user_pokemon.to_dict()}), 200


@app.route('/mypokemon/', methods=['DELETE'])
@jwt_required()
def release_pokemon():
    data = request.get_json(silent=True) or {}
    user_id = int(get_jwt_identity())
    up_id = data.get('id')

    if not up_id:
        return jsonify({'error': 'id is required'}), 400

    user_pokemon = UserPokemon.query.filter_by(id=up_id, user_id=user_id).first()
    if not user_pokemon:
        return jsonify({'error': f'Entry {up_id} not found or does not belong to you'}), 404

    released_name = user_pokemon.name
    db.session.delete(user_pokemon)
    db.session.commit()
    return jsonify({'message': f'{released_name} has been released'}), 200


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Method not allowed'}), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'An unexpected server error occurred'}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080, debug=True)


