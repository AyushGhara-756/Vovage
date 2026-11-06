from flask import Flask
from .src.routes.analysis import analysis_bp
from .src.routes.test import test_bp
from .src.routes.structure import structure_bp

app = Flask(__name__)

app.register_blueprint(test_bp)
app.register_blueprint(structure_bp)
app.register_blueprint(analysis_bp)

if __name__ == '__main__':
    app.run(port=6050)
