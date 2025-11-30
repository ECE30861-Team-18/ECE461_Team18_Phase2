import os
import sys
import json
import pytest
import logging
from unittest.mock import patch, MagicMock
from io import BytesIO

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Also add the app/ directory so modules that use top-level imports (e.g. `from metric import Metric`) can be found
app_dir = os.path.join(project_root, 'app')
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from app.submetrics import PerformanceMetric

# Ensure logs directory exists
os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'logs'), exist_ok=True)
LOG_PATH = os.path.join(os.path.dirname(__file__), '..', 'logs', 'test_performance_metric.log')

# Configure test logging to write to logs/test_performance_metric.log
logger = logging.getLogger('test_performance_metric')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(LOG_PATH, mode='w', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
# if not logger.handlers:
logger.handlers = []
logger.addHandler(file_handler)


@pytest.fixture(autouse=True)
def quiet_logging():
    # Keep the app logs quieter during tests but still allow our test logger to output
    logging.getLogger('app').setLevel(logging.WARNING)


def create_bedrock_response(content):
    """Helper to create a mock Bedrock response"""
    response_body = {
        'content': [{'text': content}]
    }
    mock_response = {
        'body': BytesIO(json.dumps(response_body).encode('utf-8'))
    }
    return mock_response


def create_bedrock_client_mock(response=None, exception=None):
    """Helper to create a mock Bedrock client"""
    mock_client = MagicMock()
    if exception:
        mock_client.invoke_model.side_effect = exception
    elif response:
        mock_client.invoke_model.return_value = response
    return mock_client


def test_valid_response_parses_score():
    logger.info('Starting test_valid_response_parses_score')
    pm = PerformanceMetric()

    bedrock_response = create_bedrock_response('0.85\nExplanation here')
    mock_client = create_bedrock_client_mock(response=bedrock_response)

    with patch('app.submetrics.boto3.client', return_value=mock_client):
        score = pm._evaluate_performance_in_readme('dummy readme')
        assert pytest.approx(score, rel=1e-3) == 0.85
    logger.info('Finished test_valid_response_parses_score')


def test_bedrock_exception_returns_zero():
    logger.info('Starting test_bedrock_exception_returns_zero')
    pm = PerformanceMetric()

    # Simulate Bedrock API error
    mock_client = create_bedrock_client_mock(exception=Exception('Bedrock API error'))

    with patch('app.submetrics.boto3.client', return_value=mock_client):
        score = pm._evaluate_performance_in_readme('dummy readme')
        assert score == 0.0
    logger.info('Finished test_bedrock_exception_returns_zero')


def test_malformed_json_returns_zero():
    logger.info('Starting test_malformed_json_returns_zero')
    pm = PerformanceMetric()

    # Simulate malformed JSON in Bedrock response body
    mock_response = {'body': BytesIO(b'not valid json')}
    mock_client = create_bedrock_client_mock(response=mock_response)

    with patch('app.submetrics.boto3.client', return_value=mock_client):
        score = pm._evaluate_performance_in_readme('dummy readme')
        assert score == 0.0
    logger.info('Finished test_malformed_json_returns_zero')


def test_successful_content_response():
    logger.info('Starting test_successful_content_response')
    pm = PerformanceMetric()

    bedrock_response = create_bedrock_response('0.72\nSome note')
    mock_client = create_bedrock_client_mock(response=bedrock_response)

    with patch('app.submetrics.boto3.client', return_value=mock_client):
        score = pm._evaluate_performance_in_readme('dummy readme')
        assert pytest.approx(score, rel=1e-3) == 0.72
    logger.info('Finished test_successful_content_response')


def test_numeric_without_newline_returns_zero():
    logger.info('Starting test_numeric_without_newline_returns_zero')
    pm = PerformanceMetric()
    # content without newline: regex expects newline after number, so returns 0.0
    bedrock_response = create_bedrock_response('0.99')
    mock_client = create_bedrock_client_mock(response=bedrock_response)

    with patch('app.submetrics.boto3.client', return_value=mock_client):
        score = pm._evaluate_performance_in_readme('dummy readme')
        assert score == 0.0
    logger.info('Finished test_numeric_without_newline_returns_zero')


def test_missing_content_field_returns_zero():
    logger.info('Starting test_missing_content_field_returns_zero')
    pm = PerformanceMetric()
    # Bedrock response missing 'content' field
    mock_response = {'body': BytesIO(json.dumps({'wrong_field': 'value'}).encode('utf-8'))}
    mock_client = create_bedrock_client_mock(response=mock_response)

    with patch('app.submetrics.boto3.client', return_value=mock_client):
        score = pm._evaluate_performance_in_readme('dummy readme')
        assert score == 0.0
    logger.info('Finished test_missing_content_field_returns_zero')


def test_client_initialization_error_returns_zero():
    logger.info('Starting test_client_initialization_error_returns_zero')
    pm = PerformanceMetric()
    # Simulate error during boto3 client initialization
    with patch('app.submetrics.boto3.client', side_effect=Exception('AWS credentials error')):
        score = pm._evaluate_performance_in_readme('dummy readme')
        assert score == 0.0
    logger.info('Finished test_client_initialization_error_returns_zero')


if __name__ == '__main__':
    # Allow running the tests module directly which will invoke pytest programmatically
    # and still create logs in logs/metric_tests.log
    logger.info('Executing tests via __main__')
    sys.exit(pytest.main([os.path.abspath(__file__), '-q']))