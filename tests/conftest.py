import pytest

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "workbench.sqlite3"))
    app.config.update(TESTING=True)
    return app.test_client()
