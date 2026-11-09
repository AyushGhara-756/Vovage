from flask import Flask
from .src.routes.flights import flight_bp
from .src.routes.hotels import hotels_bp

app = Flask(__name__)

app.register_blueprint(flight_bp)
app.register_blueprint(hotels_bp)


if __name__ == "__main__":
    app.run(port=6050)