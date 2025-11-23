import os 
import time
import json
from typing import * 
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from metric import Metric
from submetrics import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logger.info("metric_calculator initialized")

class MetricCalculator:
    """
    Calculates all metrics for a model in parallel and computes net score.
    Handles timing for individual metrics and overall calculation.
    """
    
    def __init__(self) -> None:
        """Initialize all metric calculators with appropriate weights."""
        self.metrics: List[Metric] = [
            SizeMetric(),
            LicenseMetric(), 
            RampUpMetric(),
            BusFactorMetric(),
            AvailableScoreMetric(),
            DatasetQualityMetric(),
            CodeQualityMetric(),
            PerformanceMetric()
        ]
        
        # Configure weights based on Sarah's priorities from spec
        self._configure_weights()
        logger.info("Metrics initialized with submetrics and weights")
    
    def _configure_weights(self) -> None:
        """Configure metric weights based on Sarah's stated priorities."""
        # Sarah's concerns prioritized: ramp-up time, quality, documentation, maintainability
        weight_config: Dict[str, float] = {
            "ramp_up_time": 0.20,      # High priority - ease of use
            "license": 0.15,           # High priority - legal compliance  
            "dataset_and_code_score": 0.15,  # High priority - documentation
            "performance_claims": 0.15, # High priority - evidence of quality
            "bus_factor": 0.10,        # Medium priority - maintainability
            "code_quality": 0.10,      # Medium priority - code standards
            "dataset_quality": 0.10,   # Medium priority - data quality
            "size_score": 0.05        # Lower priority - deployment consideration
        }
        
        for metric in self.metrics:
            metric.weight = weight_config[metric.name]
            # metric.weight = 0.125
    
    def calculate_all_metrics(self, model_data: Dict[str, Any], category: str = "MODEL") -> Dict[str, Any]:
        """
        Calculate all metrics for a model in parallel and return complete results.
        
        Args:
            model_data: JSON string containing model information from HuggingFace API
            category: Type of resource being evaluated (MODEL, DATASET, CODE)
            
        Returns:
            Dictionary containing all metric scores, latencies, and net score
        """
        start_time = time.time()
        
        # Initialize results structure
        results = {
            "category": category,
            "net_score": 0.0,
            "net_score_latency": 0
        }
        
        # Execute all metrics in parallel
        metric_results = self._calculate_metrics_parallel(model_data)
        
        # Process results and calculate net score
        net_score = 0.0
        for metric, (score, latency) in metric_results.items():
            
            # Handle size metric special case (returns dict)
            if isinstance(score, dict):
                results[f"{metric.name}"] = score
                # For net score, use average of hardware compatibility
                avg_score = sum(score.values()) / len(score) if score else 0.0
                net_score += avg_score * metric.weight
            else:
                results[metric.name] = float(score)
                net_score += float(score) * metric.weight
            
            results[f"{metric.name}_latency"] = latency
        
        # Finalize net score and latency
        results["net_score"] = round(net_score, 3) 
        results["net_score_latency"] = int((time.time() - start_time) * 1000)
        
        return results
    
    def _calculate_metrics_parallel(self, model_data: Dict[str, Any]) -> Dict[Metric, Tuple[Any, int]]:
        """
        Execute all metric calculations in parallel using ThreadPoolExecutor.
        
        Args:
            model_data: Model information as JSON string
            
        Returns:
            Dictionary mapping metrics to (score, latency) tuples
        """
        results = {}
        
        # Determine optimal thread count (don't exceed number of metrics or system cores)
        max_workers: int = min(len(self.metrics), os.cpu_count() or 4)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all metric calculations
            future_to_metric = {
                executor.submit(self._safe_calculate_metric, metric, model_data): metric
                for metric in self.metrics
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_metric):
                metric = future_to_metric[future]
                try:
                    score, latency = future.result(timeout=30)  # 30 second timeout per metric
                    results[metric] = (score, latency)
                except Exception as e:
                    logger.warning(f"Metric {metric.name} failed: {e}")
                    results[metric] = (0.0, 0)  # Default values on failure
        
        return results
    
    def _safe_calculate_metric(self, metric: Metric, model_data: Dict[str, Any]) -> Tuple[Any, int]:
        """
        Safely calculate a single metric with error handling and timing.
        
        Args:
            metric: The metric calculator to run
            model_data: Model information
            
        Returns:
            Tuple of (score, latency_ms)
        """
        try:
            # Normalize input: parse JSON string into dict if necessary
            if isinstance(model_data, str):
                try:
                    model_data = json.loads(model_data)
                except Exception:
                    # If parsing fails, proceed with original value to preserve previous behavior
                    pass
            # Calculate the metric score
            score = metric.calculate_metric(model_data)
            
            # Get the latency from the metric
            latency = metric.calculate_latency()
            
            return score, latency
            
        except Exception as e:
            logger.error(f"Error calculating {metric.name}: {e}")
            return 0.0, 0
    
    def get_metric_weights(self) -> Dict[str, float]:
        """Return the current metric weights for transparency."""
        if not self.metrics:
            return {}
        return {metric.name: metric.weight for metric in self.metrics}
