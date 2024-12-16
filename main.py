from website import create_app

app = create_app()
with app.app_context():
    from website import db
    db.create_all()

if __name__ == "__main__":
   app.run(debug=True, host='127.0.0.1', port=5004)

    