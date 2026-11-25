import os

from flask import Flask, jsonify, render_template
from werkzeug.exceptions import RequestEntityTooLarge

from app.accounting.routes import accounting
from app.accounting.store import AccountingStore
from app.catalog import SPEC
from app.config import MAX_FILE, ROOT
from app.errors import DomainIssue, error_response
from app.review.store import Store
from app.routes import api


def create_app(database=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE + 64 * 1024
    db_path = database or os.getenv("WORKBENCH_DB", str(ROOT / "instance" / "workbench.sqlite3"))
    app.extensions["runs"] = Store(db_path)
    app.extensions["accounting"] = AccountingStore(db_path)
    app.register_error_handler(DomainIssue, error_response)
    app.register_error_handler(RequestEntityTooLarge, lambda _: error_response(DomainIssue("FILE_TOO_LARGE", 413)))
    app.register_blueprint(api)
    app.register_blueprint(accounting)

    @app.get("/")
    def home():
        return render_template("index.html", p=SPEC)

    @app.get("/healthz")
    def health():
        return jsonify(status="ok")

    return app


app = create_app()
