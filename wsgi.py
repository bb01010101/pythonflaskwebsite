from website import create_app
from website import socketio

app = create_app()
application = socketio.WSGIApp(app)

# This is what Gunicorn uses
wsgi_app = application

if __name__ == "__main__":
    socketio.run(app) 