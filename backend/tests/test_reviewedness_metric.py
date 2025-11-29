import os
import sys
import json
import pytest
import logging
import requests
from unittest.mock import patch

# Ensure project and app paths are importable
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
app_dir = os.path.join(project_root, 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from app.submetrics import ReviewedenessMetric

# Ensure logs directory exists
os.makedirs(os.path.join(project_root, 'logs'), exist_ok=True)
LOG_PATH = os.path.join(project_root, 'logs', 'test_reviewedness_metric.log')

# Configure test logging
logger = logging.getLogger('test_reviewedness_metric')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(LOG_PATH, mode='w', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.handlers = []
logger.addHandler(file_handler)


@pytest.fixture(autouse=True)
def quiet_logging():
    # Reduce noise from application logs
    logging.getLogger('app').setLevel(logging.WARNING)


class DummyResp:
    """Mock class to simulate requests.post() responses for GraphQL API."""
    def __init__(self, status_code=200, json_obj=None, text=None, json_exc=None):
        self.status_code = status_code
        self._json = json_obj
        self.text = text if text is not None else (json.dumps(json_obj) if json_obj is not None else '')
        self._json_exc = json_exc

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error")
        return None


def test_valid_graphql_response_computes_fraction():
    """Should compute correct reviewed fraction from valid GraphQL JSON."""
    metric = ReviewedenessMetric()

    # Mock GraphQL JSON payload — 3 PRs, 2 of them reviewed
    mock_json = {
        "data": {
            "repository": {
                "pullRequests": {
                    "nodes": [
                        {"number": 1, "reviews": {"totalCount": 2}},
                        {"number": 2, "reviews": {"totalCount": 0}},
                        {"number": 3, "reviews": {"totalCount": 1}},
                    ]
                }
            }
        }
    }

    # Patch the correct import path for requests.post (since ReviewedenessMetric is in app/submetrics.py)
    with patch('app.submetrics.requests.post', return_value=DummyResp(status_code=200, json_obj=mock_json)):
        score = metric._get_reviewed_fraction("https://github.com/huggingface/transformers")
        assert score == pytest.approx(2/3, rel=1e-3)


def test_graphql_non_200_status_returns_zero():
    """If API returns non-200, score should be 0.0."""
    logger.info('Starting test_graphql_non_200_status_returns_zero')
    metric = ReviewedenessMetric()
    with patch('app.submetrics.requests.post', return_value=DummyResp(status_code=403, json_obj={"message": "Forbidden"})):
        score = metric._get_reviewed_fraction("https://github.com/huggingface/transformers")
        assert score == 0.0
    logger.info('Finished test_graphql_non_200_status_returns_zero')


def test_graphql_errors_field_returns_zero():
    """If GraphQL returns 'errors' key, method should return 0.0."""
    logger.info('Starting test_graphql_errors_field_returns_zero')
    metric = ReviewedenessMetric()
    mock_json = {"errors": [{"message": "Bad credentials"}]}
    with patch('app.submetrics.requests.post', return_value=DummyResp(status_code=200, json_obj=mock_json)):
        score = metric._get_reviewed_fraction("https://github.com/huggingface/transformers")
        assert score == 0.0
    logger.info('Finished test_graphql_errors_field_returns_zero')


def test_invalid_repo_url_returns_zero():
    """Invalid GitHub URL format should return 0.0."""
    logger.info('Starting test_invalid_repo_url_returns_zero')
    metric = ReviewedenessMetric()
    score = metric._get_reviewed_fraction("https://huggingface.co/transformers")
    assert score == 0.0
    logger.info('Finished test_invalid_repo_url_returns_zero')


def test_graphql_json_raises_exception_returns_zero():
    """Simulate .json() raising a ValueError → should return 0.0."""
    logger.info('Starting test_graphql_json_raises_exception_returns_zero')
    metric = ReviewedenessMetric()
    with patch('app.submetrics.requests.post', return_value=DummyResp(status_code=200, json_exc=ValueError("bad json"))):
        score = metric._get_reviewed_fraction("https://github.com/huggingface/transformers")
        assert score == 0.0
    logger.info('Finished test_graphql_json_raises_exception_returns_zero')


def test_graphql_exception_handling_returns_zero():
    """Simulate network exception → should return 0.0."""
    logger.info('Starting test_graphql_exception_handling_returns_zero')
    metric = ReviewedenessMetric()
    with patch('app.submetrics.requests.post', side_effect=requests.ConnectionError("Network fail")):
        score = metric._get_reviewed_fraction("https://github.com/huggingface/transformers")
        assert score == 0.0
    logger.info('Finished test_graphql_exception_handling_returns_zero')


if __name__ == '__main__':
    logger.info('Executing tests via __main__')
    sys.exit(pytest.main([os.path.abspath(__file__), '-q']))