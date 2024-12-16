from website import create_app
from website import socketio

app = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=True)

    