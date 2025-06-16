from app import create_app, db
from flask_migrate import Migrate
from models import User, Account, Loan

app = create_app()
migrate = Migrate(app, db)

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Account': Account, 'Loan': Loan}

if __name__ == '__main__':
    app.run(debug=True)
