import click
import csv
from tabulate import tabulate
from App import db, User, Pokemon, UserPokemon
from App import app
from App.app import initialize_db

@app.cli.command("init", help="Creates and initializes the database")
def initialize_db():
    with app.app_context():
        db.create_all()
    print("Database Initialized!")


app.cli.add_command(initialize_db)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
