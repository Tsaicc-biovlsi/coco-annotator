import os
import tempfile

import pytest

# Tests run fully in-process: in-memory MongoDB (mongomock), Celery tasks
# executed eagerly and an in-memory message queue. Environment variables
# that are already set (e.g. in CI) take precedence.
_DATASETS = tempfile.mkdtemp(prefix="coco-annotator-tests-")
os.environ.setdefault("MONGODB_HOST", "mongomock://localhost/flask")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("DATASET_DIRECTORY", _DATASETS + "/")
os.environ.setdefault("LOGIN_DISABLED", "true")
os.environ.setdefault("SAM_CHECKPOINT", "/nonexistent/sam.pth")

from webserver import app  # noqa: E402


@pytest.fixture
def client():
    test_client = app.test_client()
    return test_client


@pytest.fixture(scope="session")
def dataset_directory():
    return os.environ["DATASET_DIRECTORY"]
