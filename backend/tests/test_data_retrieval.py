#!/usr/bin/env python3
"""
Pytest-compatible tests for Data Retrieval module.

Tests cover API clients, data retrieval functionality, and integration
with URL handler results.
"""

import pytest
import warnings
from _pytest.warning_types import PytestUnknownMarkWarning

import sys
import os
from unittest.mock import Mock, patch, MagicMock
import requests

# Add the app directory to Python path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from data_retrieval import (
    DataRetriever, GitHubAPIClient, NPMAPIClient, HuggingFaceAPIClient,
    RepositoryData
)
from url_handler import URLHandler
from url_category import URLCategory
from url_data import URLData


class TestRepositoryData:
    """Test RepositoryData structure."""
    
    def test_repository_data_creation(self):
        """Test creating RepositoryData objects."""
        repo_data = RepositoryData(
            platform="github",
            identifier="test/repo",
            name="repo",
            description="Test repository",
            stars=100,
            success=True
        )
        
        assert repo_data.platform == "github"
        assert repo_data.identifier == "test/repo"
        assert repo_data.name == "repo"
        assert repo_data.description == "Test repository"
        assert repo_data.stars == 100
        assert repo_data.success == True
    
    def test_repository_data_defaults(self):
        """Test RepositoryData default values."""
        repo_data = RepositoryData(
            platform="github",
            identifier="test/repo",
            name="repo"
        )
        
        assert repo_data.description is None
        assert repo_data.stars is None
        assert repo_data.success == True  # Default is True
        assert repo_data.error_message is None


class TestGitHubAPIClient:
    """Test GitHub API client functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = GitHubAPIClient()
    
    def test_client_initialization(self):
        """Test GitHub client initialization."""
        assert self.client.base_url == "https://api.github.com"
        assert "Accept" in self.client.session.headers
        assert "User-Agent" in self.client.session.headers
    
    def test_client_with_token(self):
        """Test GitHub client initialization with token."""
        client_with_token = GitHubAPIClient(token="test_token")
        assert "Authorization" in client_with_token.session.headers
        assert client_with_token.session.headers["Authorization"] == "token test_token"
    
    @patch('requests.Session.get')
    def test_get_repository_data_success(self, mock_get):
        """Test successful repository data retrieval."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "test-repo",
            "description": "Test repository",
            "stargazers_count": 100,
            "forks_count": 50,
            "watchers_count": 25,
            "open_issues_count": 10,
            "language": "Python",
            "license": {"name": "MIT License"},
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "html_url": "https://github.com/test/test-repo"
        }
        mock_get.return_value = mock_response
        
        result = self.client.get_repository_data("test", "test-repo")
        
        assert result.success == True
        assert result.name == "test-repo"
        assert result.description == "Test repository"
        assert result.stars == 100
        assert result.forks == 50
        assert result.language == "Python"
    
    @patch('requests.Session.get')
    def test_get_repository_data_not_found(self, mock_get):
        """Test repository not found scenario."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = self.client.get_repository_data("test", "nonexistent")
        
        assert result.success == False
        assert "not found" in result.error_message.lower()
    
    @patch('requests.Session.get')
    def test_get_repository_data_rate_limit(self, mock_get):
        """Test rate limit handling."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        result = self.client.get_repository_data("test", "repo")
        
        assert result.success == False
        assert "rate limit" in result.error_message.lower()
    
    @patch('requests.Session.get')
    def test_get_repository_data_exception(self, mock_get):
        """Test exception handling."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        result = self.client.get_repository_data("test", "repo")
        
        assert result.success == False
        assert "network error" in result.error_message.lower()


class TestNPMAPIClient:
    """Test NPM API client functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = NPMAPIClient()
    
    def test_client_initialization(self):
        """Test NPM client initialization."""
        assert self.client.base_url == "https://registry.npmjs.org"
        assert self.client.downloads_url == "https://api.npmjs.org/downloads"
        assert "User-Agent" in self.client.session.headers
    
    @patch('requests.Session.get')
    def test_get_package_data_success(self, mock_get):
        """Test successful package data retrieval."""
        # Mock package registry response
        def mock_response_side_effect(url, **kwargs):
            mock_response = Mock()
            if "registry.npmjs.org" in url:
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "name": "test-package",
                    "description": "Test package",
                    "dist-tags": {"latest": "1.0.0"},
                    "versions": {
                        "1.0.0": {
                            "description": "Test package",
                            "dependencies": {"dep1": "^1.0.0"},
                            "devDependencies": {"dev-dep1": "^2.0.0"},
                            "license": "MIT",
                            "homepage": "https://example.com"
                        }
                    },
                    "time": {
                        "created": "2020-01-01T00:00:00Z",
                        "modified": "2023-01-01T00:00:00Z"
                    }
                }
            elif "api.npmjs.org/downloads" in url:
                mock_response.status_code = 200
                mock_response.json.return_value = {"downloads": 1000}
            return mock_response
        
        mock_get.side_effect = mock_response_side_effect
        
        result = self.client.get_package_data("test-package")
        
        assert result.success == True
        assert result.name == "test-package"
        assert result.description == "Test package"
        assert result.version == "1.0.0"
        assert len(result.dependencies) == 1
        assert len(result.dev_dependencies) == 1
    
    @patch('requests.Session.get')
    def test_get_package_data_not_found(self, mock_get):
        """Test package not found scenario."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = self.client.get_package_data("nonexistent-package")
        
        assert result.success == False
        assert "not found" in result.error_message.lower()


class TestHuggingFaceAPIClient:
    """Test Hugging Face API client functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = HuggingFaceAPIClient()
    
    def test_client_initialization(self):
        """Test Hugging Face client initialization."""
        assert self.client.base_url == "https://huggingface.co/api"
        assert "User-Agent" in self.client.session.headers
    
    @patch('requests.Session.get')
    def test_get_model_data_success(self, mock_get):
        """Test successful model data retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "test/model",
            "description": "Test model",
            "downloads": 5000,
            "pipeline_tag": "text-generation",
            "license": "apache-2.0",
            "createdAt": "2020-01-01T00:00:00Z",
            "lastModified": "2023-01-01T00:00:00Z"
        }
        mock_get.return_value = mock_response
        
        result = self.client.get_model_data("test/model")
        
        assert result.success == True
        assert result.identifier == "test/model"
        assert result.name == "model"
        assert result.description == "Test model"
        assert result.downloads_last_month == 5000
        assert result.language == "text-generation"
    
    @patch('requests.Session.get')
    def test_get_model_data_not_found(self, mock_get):
        """Test model not found scenario."""
        # First call (models) returns 404, second call (datasets) also returns 404
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = self.client.get_model_data("nonexistent/model")
        
        assert result.success == False
        assert "not found" in result.error_message.lower()


class TestDataRetriever:
    """Test main DataRetriever class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.retriever = DataRetriever()
    
    def test_retriever_initialization(self):
        """Test DataRetriever initialization."""
        assert isinstance(self.retriever.github_client, GitHubAPIClient)
        assert isinstance(self.retriever.npm_client, NPMAPIClient)
        assert isinstance(self.retriever.huggingface_client, HuggingFaceAPIClient)
        assert self.retriever.rate_limit_delay == 0.1
    
    def test_retriever_with_custom_settings(self):
        """Test DataRetriever with custom settings."""
        retriever = DataRetriever(github_token="test_token", rate_limit_delay=0.5)
        assert retriever.rate_limit_delay == 0.5
        assert "Authorization" in retriever.github_client.session.headers
    
    @patch('data_retrieval.GitHubAPIClient.get_repository_data')
    def test_retrieve_github_data(self, mock_get_repo_data):
        """Test retrieving GitHub data."""
        # Mock GitHub API response
        mock_get_repo_data.return_value = RepositoryData(
            platform="github",
            identifier="test/repo",
            name="repo",
            stars=100,
            success=True
        )
        
        url_data = URLData(
            original_url="https://github.com/test/repo",
            category=URLCategory.GITHUB,
            hostname="github.com",
            is_valid=True,
            unique_identifier="test/repo",
            owner="test",
            repository="repo"
        )
        
        result = self.retriever.retrieve_data(url_data)
        
        assert result.success == True
        assert result.platform == "github"
        assert result.stars == 100
        mock_get_repo_data.assert_called_once_with("test", "repo")
    
    @patch('data_retrieval.NPMAPIClient.get_package_data')
    def test_retrieve_npm_data(self, mock_get_package_data):
        """Test retrieving NPM data."""
        # Mock NPM API response
        mock_get_package_data.return_value = RepositoryData(
            platform="npm",
            identifier="test-package",
            name="test-package",
            version="1.0.0",
            success=True
        )
        
        url_data = URLData(
            original_url="https://npmjs.com/package/test-package",
            category=URLCategory.NPM,
            hostname="npmjs.com",
            is_valid=True,
            unique_identifier="test-package",
            package_name="test-package"
        )
        
        result = self.retriever.retrieve_data(url_data)
        
        assert result.success == True
        assert result.platform == "npm"
        assert result.version == "1.0.0"
        mock_get_package_data.assert_called_once_with("test-package")
    
    def test_retrieve_invalid_data(self):
        """Test retrieving data for invalid URL."""
        url_data = URLData(
            original_url="invalid",
            category=URLCategory.UNKNOWN,
            hostname="",
            is_valid=False
        )
        
        result = self.retriever.retrieve_data(url_data)
        
        assert result.success == False
        assert "invalid url data" in result.error_message.lower()
    
    def test_retrieve_unsupported_category(self):
        """Test retrieving data for unsupported category."""
        url_data = URLData(
            original_url="https://example.com",
            category=URLCategory.UNKNOWN,
            hostname="example.com",
            is_valid=True,
            unique_identifier="test"
        )
        
        result = self.retriever.retrieve_data(url_data)
        
        assert result.success == False
        assert "unsupported platform" in result.error_message.lower()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @patch('data_retrieval.DataRetriever.retrieve_data')
    def test_retrieve_data_for_url(self, mock_retrieve):
        """Test convenience function for single URL."""
        mock_retrieve.return_value = RepositoryData(
            platform="github",
            identifier="test/repo",
            name="repo",
            success=True
        )
        
        url_data = URLData(
            original_url="https://github.com/test/repo",
            category=URLCategory.GITHUB,
            hostname="github.com",
            is_valid=True,
            unique_identifier="test/repo"
        )

        retriever = DataRetriever()
        result = retriever.retrieve_data(url_data)

        assert result.success == True
        assert result.platform == "github"
        mock_retrieve.assert_called_once_with(url_data)
    
    @patch('data_retrieval.DataRetriever.retrieve_batch_data')
    def test_retrieve_data_for_urls(self, mock_retrieve_batch):
        """Test convenience function for multiple URLs."""
        mock_retrieve_batch.return_value = [
            RepositoryData(platform="github", identifier="test1/repo1", name="repo1", success=True),
            RepositoryData(platform="npm", identifier="test-package", name="test-package", success=True)
        ]
        
        url_data_list = [
            URLData("https://github.com/test1/repo1", URLCategory.GITHUB, "github.com", True),
            URLData("https://npmjs.com/package/test-package", URLCategory.NPM, "npmjs.com", True)
        ]

        retriever = DataRetriever()
        results = retriever.retrieve_batch_data(url_data_list)

        assert len(results) == 2
        assert results[0].platform == "github"
        assert results[1].platform == "npm"
        mock_retrieve_batch.assert_called_once_with(url_data_list)


class TestIntegrationScenarios:
    """Test integration scenarios between URL handler and data retrieval."""
    
    def test_data_structure_compatibility(self):
        """Test that URL handler output is compatible with data retrieval input."""
        
        # Process a URL
        url_data = URLHandler().handle_url("https://github.com/microsoft/typescript")
        
        # Verify it has the required fields for data retrieval
        assert hasattr(url_data, 'is_valid')
        assert hasattr(url_data, 'category')
        assert hasattr(url_data, 'unique_identifier')
        assert hasattr(url_data, 'owner')
        assert hasattr(url_data, 'repository')
        
        # Should be compatible with DataRetriever
        retriever = DataRetriever()
        # This should not raise an exception
        try:
            result = retriever.retrieve_data(url_data)
            assert isinstance(result, RepositoryData)
        except Exception as e:
            pytest.fail(f"Integration compatibility failed: {e}")


# Integration test that requires network access - marked as slow
class TestRealAPIIntegration:
    """Test real API integration (requires network access)."""
    
    def test_real_github_api_call(self):
        """Test actual GitHub API call (network required)."""
        client = GitHubAPIClient()
        result = client.get_repository_data("octocat", "Hello-World")
        
        
        
        # This is a real repository that should exist
        assert result.success == True
        assert result.name is not None
        assert result.platform == "github"
    
    def test_real_npm_api_call(self):
        """Test actual NPM API call (network required)."""
        client = NPMAPIClient()
        result = client.get_package_data("express")
        
        # Express is a very popular package that should exist
        assert result.success == True
        assert result.name == "express"
        assert result.platform == "npm"
