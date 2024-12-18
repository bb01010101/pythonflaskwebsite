from website import create_app, db
from flask_migrate import Migrate

app = create_app()
migrate = Migrate(app, db)

if __name__ == '__main__':
    # Get the PORT from the environment variable, default to 5000 if not set
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)


    