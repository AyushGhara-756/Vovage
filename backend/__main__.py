from flask import Flask
from .src.routes.test import test_bp

app = Flask(__name__)

app.register_blueprint(test_bp)

if __name__ == '__main__':
    app.run(port=6050)
