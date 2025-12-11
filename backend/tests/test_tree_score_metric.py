import pytest
import json
import sys
import os
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from submetrics import TreeScoreMetric


class TestTreeScoreMetric:
    """Test suite for TreeScore metric calculation."""
    
    def test_no_artifact_id(self):
        """Test TreeScore returns 0.0 when no artifact_id is provided."""
        metric = TreeScoreMetric()
        model_info = {
            "name": "test-model",
            "readme": "Some readme content"
        }
        
        score = metric.calculate_metric(model_info)
        
        assert score == 0.0
        assert metric.calculate_latency() >= 0
    
    def test_no_parents(self):
        """Test TreeScore returns 0.0 when model has no parents."""
        metric = TreeScoreMetric()
        model_info = {
            "artifact_id": 123,
            "name": "test-model"
        }
        
        with patch('rds_connection.run_query') as mock_query:
            # Mock artifact query - no auto_lineage, no relationships
            mock_query.return_value = [{
                "metadata": json.dumps({"auto_lineage": []}),
                "ratings": json.dumps({})
            }]
            
            score = metric.calculate_metric(model_info)
            
            assert score == 0.0
            assert metric.calculate_latency() >= 0
    
    def test_single_parent_via_auto_lineage(self):
        """Test TreeScore with one parent from auto_lineage."""
        metric = TreeScoreMetric()
        model_info = {
            "artifact_id": 123,
            "name": "fine-tuned-model"
        }
        
        with patch('rds_connection.run_query') as mock_query:
            def query_side_effect(sql, params=None, fetch=False):
                # First call: get artifact metadata
                if "metadata" in sql and params == (123,):
                    return [{
                        "metadata": json.dumps({
                            "auto_lineage": [{
                                "artifact_id": "456",
                                "relationship": "base_model",
                                "placeholder": False
                            }]
                        }),
                        "ratings": json.dumps({})
                    }]
                # Second call: get parent net_score
                elif "net_score" in sql and params == ("456",):
                    return [{"net_score": 0.75}]
                # Third call: check relationships table
                elif "artifact_relationships" in sql:
                    return []
                return []
            
            mock_query.side_effect = query_side_effect
            
            score = metric.calculate_metric(model_info)
            
            assert score == 0.75
            assert metric.calculate_latency() >= 0
    
    def test_multiple_parents_average(self):
        """Test TreeScore averages multiple parent scores."""
        metric = TreeScoreMetric()
        model_info = {
            "artifact_id": 123,
            "name": "multi-parent-model"
        }
        
        with patch('rds_connection.run_query') as mock_query:
            def query_side_effect(sql, params=None, fetch=False):
                # First call: get artifact metadata
                if "metadata" in sql and params == (123,):
                    return [{
                        "metadata": json.dumps({
                            "auto_lineage": [
                                {
                                    "artifact_id": "456",
                                    "relationship": "base_model",
                                    "placeholder": False
                                },
                                {
                                    "artifact_id": "789",
                                    "relationship": "parent_model",
                                    "placeholder": False
                                }
                            ]
                        }),
                        "ratings": json.dumps({})
                    }]
                # Second call: get first parent net_score
                elif "net_score" in sql and params == ("456",):
                    return [{"net_score": 0.8}]
                # Third call: get second parent net_score
                elif "net_score" in sql and params == ("789",):
                    return [{"net_score": 0.6}]
                # Fourth call: check relationships table
                elif "artifact_relationships" in sql:
                    return []
                return []
            
            mock_query.side_effect = query_side_effect
            
            score = metric.calculate_metric(model_info)
            
            # Average of 0.8 and 0.6 = 0.7
            assert score == 0.7
            assert metric.calculate_latency() >= 0
    
    def test_placeholder_parent_resolution(self):
        """Test TreeScore resolves placeholder parents by name."""
        metric = TreeScoreMetric()
        model_info = {
            "artifact_id": 123,
            "name": "derived-model"
        }
        
        with patch('rds_connection.run_query') as mock_query:
            def query_side_effect(sql, params=None, fetch=False):
                # First call: get artifact metadata
                if "metadata" in sql and params == (123,):
                    return [{
                        "metadata": json.dumps({
                            "auto_lineage": [{
                                "artifact_id": "bert-base-uncased",
                                "relationship": "base_model",
                                "placeholder": True
                            }]
                        }),
                        "ratings": json.dumps({})
                    }]
                # Second call: resolve placeholder by name
                elif "name" in sql and params == ("bert-base-uncased",):
                    return [{"id": 999, "net_score": 0.85}]
                # Third call: check relationships table
                elif "artifact_relationships" in sql:
                    return []
                return []
            
            mock_query.side_effect = query_side_effect
            
            score = metric.calculate_metric(model_info)
            
            assert score == 0.85
            assert metric.calculate_latency() >= 0
    
    def test_parent_from_relationships_table(self):
        """Test TreeScore includes parents from artifact_relationships table."""
        metric = TreeScoreMetric()
        model_info = {
            "artifact_id": 123,
            "name": "test-model"
        }
        
        with patch('rds_connection.run_query') as mock_query:
            def query_side_effect(sql, params=None, fetch=False):
                # First call: get artifact metadata (no auto_lineage)
                if "metadata" in sql and params == (123,):
                    return [{
                        "metadata": json.dumps({"auto_lineage": []}),
                        "ratings": json.dumps({})
                    }]
                # Second call: check relationships table
                elif "artifact_relationships" in sql:
                    return [{"net_score": 0.9}]
                return []
            
            mock_query.side_effect = query_side_effect
            
            score = metric.calculate_metric(model_info)
            
            assert score == 0.9
            assert metric.calculate_latency() >= 0
    
    def test_combined_sources(self):
        """Test TreeScore combines parents from auto_lineage and relationships table."""
        metric = TreeScoreMetric()
        model_info = {
            "artifact_id": 123,
            "name": "complex-model"
        }
        
        with patch('rds_connection.run_query') as mock_query:
            def query_side_effect(sql, params=None, fetch=False):
                # First call: get artifact metadata
                if "metadata" in sql and params == (123,):
                    return [{
                        "metadata": json.dumps({
                            "auto_lineage": [{
                                "artifact_id": "456",
                                "relationship": "base_model",
                                "placeholder": False
                            }]
                        }),
                        "ratings": json.dumps({})
                    }]
                # Second call: get parent from auto_lineage
                elif "net_score" in sql and params == ("456",):
                    return [{"net_score": 0.7}]
                # Third call: get parent from relationships table
                elif "artifact_relationships" in sql:
                    return [{"net_score": 0.9}]
                return []
            
            mock_query.side_effect = query_side_effect
            
            score = metric.calculate_metric(model_info)
            
            # Average of 0.7 and 0.9 = 0.8
            assert score == 0.8
            assert metric.calculate_latency() >= 0
    
    def test_artifact_id_from_metadata(self):
        """Test TreeScore extracts artifact_id from nested metadata."""
        metric = TreeScoreMetric()
        model_info = {
            "name": "test-model",
            "metadata": json.dumps({"artifact_id": 456})
        }
        
        with patch('rds_connection.run_query') as mock_query:
            # Mock no parents for simplicity
            mock_query.return_value = [{
                "metadata": json.dumps({"auto_lineage": []}),
                "ratings": json.dumps({})
            }]
            
            score = metric.calculate_metric(model_info)
            
            # Should not crash, should call query with artifact_id 456
            assert score == 0.0
            assert mock_query.called
    
    def test_error_handling(self):
        """Test TreeScore handles database errors gracefully."""
        metric = TreeScoreMetric()
        model_info = {
            "artifact_id": 123,
            "name": "test-model"
        }
        
        with patch('rds_connection.run_query') as mock_query:
            mock_query.side_effect = Exception("Database connection failed")
            
            score = metric.calculate_metric(model_info)
            
            assert score == 0.0
            assert metric.calculate_latency() >= 0
    
    def test_weight_is_zero(self):
        """Test TreeScore weight is 0.0 (not included in net_score)."""
        metric = TreeScoreMetric()
        
        assert metric.weight == 0.0
        assert metric.name == "tree_score"
    
    def test_clamping(self):
        """Test TreeScore clamps values between 0.0 and 1.0."""
        metric = TreeScoreMetric()
        model_info = {
            "artifact_id": 123,
            "name": "test-model"
        }
        
        with patch('rds_connection.run_query') as mock_query:
            def query_side_effect(sql, params=None, fetch=False):
                if "metadata" in sql and params == (123,):
                    return [{
                        "metadata": json.dumps({
                            "auto_lineage": [{
                                "artifact_id": "456",
                                "relationship": "base_model",
                                "placeholder": False
                            }]
                        }),
                        "ratings": json.dumps({})
                    }]
                elif "net_score" in sql and params == ("456",):
                    # Return invalid score > 1.0
                    return [{"net_score": 1.5}]
                elif "artifact_relationships" in sql:
                    return []
                return []
            
            mock_query.side_effect = query_side_effect
            
            score = metric.calculate_metric(model_info)
            
            # Should be clamped to 1.0
            assert score == 1.0
            assert metric.calculate_latency() >= 0
