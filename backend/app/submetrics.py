import os
import math
from pyexpat import model
import re
import time
import json
import requests
from datetime import datetime, timezone
from typing import * 
from metric import Metric
import subprocess
import tempfile
import sys
import textwrap
import boto3

try:
    from dotenv import load_dotenv # pyright: ignore[reportMissingImports]
    # Load .env and allow .env to override empty env vars set by the `run` script
    load_dotenv(override=True)
except Exception:
    # python-dotenv not installed; tests should still run without env overrides
    pass

# Read Gen AI Studio API key safely (may be missing). Do not raise on missing key.
GEN_AI_STUDIO_API_KEY = os.environ.get('GEN_AI_STUDIO_API_KEY')




class SizeMetric(Metric):
    """Calculates size compatibility scores for different hardware platforms"""
    
    def __init__(self) -> None:
        super().__init__()
        self.name = "size_score"
        self.weight = 0.125
        
        # Hardware compatibility thresholds in GB 
        self.hardware_limits = {
            "raspberry_pi": 8.0,
            "jetson_nano": 8.0, 
            "desktop_pc": 32.0,
            "aws_server": 128.0
        }
    
    def calculate_metric(self, model_info: Dict[str, Any]) -> Dict[str, float]:
        """Calculate size scores for each hardware type"""
        start_time = time.time()
        
        try:
            if isinstance(model_info, str):
                try:
                    model_info = json.loads(model_info)
                except Exception:
                    model_info = {}
            # Parse model size from data (expecting JSON with model info)
            model_size_gb = self._get_model_size(model_info)
            size_display = (
                f"{model_size_gb:.4f}"
                if isinstance(model_size_gb, (int, float))
                else str(model_size_gb)
            )
            scores: Dict[str, float] = {}
            for hardware, limit_gb in self.hardware_limits.items():
                # Calculate effective memory limit after accounting for OS and overhead
                if not model_size_gb:
                    usage = float('inf')
                else:
                    usage = limit_gb / model_size_gb
                scores[hardware] = usage if usage <= 1.0 else 1.0


            self._latency = int((time.time() - start_time) * 1000)
            return scores
            
        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            # Return minimum scores on error
            return {hw: 0.0 for hw in self.hardware_limits.keys()}
    
    def _get_model_size(self, model_info: Dict[str, Any]) -> float:
        """Extract model size in GB from model info"""
        # Priority 1: Sum explicit weight-file sizes retrieved from HF API
        weight_bytes = self._sum_weight_file_sizes(model_info)
        if weight_bytes > 0:
            return weight_bytes / (1024**3)

        # Priority 2: Use HuggingFace's reported storage data (can be noisy)
        storage_value = None
        for key in ("used_storage", "usedStorage"):
            if key in model_info and model_info[key]:
                storage_value = model_info[key]
                break
        if storage_value is not None:
            try:
                storage_bytes = float(storage_value)
                return storage_bytes / (1024**3)  # Convert bytes to GB
            except Exception:
                pass
        
        # # Priority 2: Try to get size from various other possible fields
        # if "size" in model_info:
        #     try:
        #         raw_size = float(model_info["size"])  # Could be bytes or GB
        #     except Exception:
        #         raw_size = 0.0
        #     # Assume bytes only if >= 1 GiB; otherwise treat as GB to avoid inflating small sizes
        #     if raw_size >= (1024**3):
        #         return raw_size / (1024**3)
        #     else:
        #         return raw_size
        # elif "model_size" in model_info:
        #     return float(model_info["model_size"])
        elif "safetensors" in model_info:
            try:
                st = model_info["safetensors"]
                # HF can return a dict with a 'total' size or a list of files
                if isinstance(st, dict):
                    total_bytes = 0.0
                    if "total" in st:
                        total_bytes = float(st.get("total") or 0)
                    elif "size" in st:
                        total_bytes = float(st.get("size") or 0)
                    return float(total_bytes) / (1024**3)
                elif isinstance(st, list):
                    total_bytes = 0.0
                    for f in st:
                        try:
                            total_bytes += float((f or {}).get("size", 0) or 0)
                        except Exception:
                            continue
                    return float(total_bytes) / (1024**3)
            except Exception:
                pass
        # As a fallback, try summing model weight files from siblings if sizes are present
        try:
            siblings = model_info.get("siblings") or []
            if isinstance(siblings, list) and siblings:
                backup_bytes = self._sum_weight_file_sizes(model_info, include_all_candidates=True)
                if backup_bytes > 0:
                    return backup_bytes / (1024**3)
        except Exception:
            pass
        # Default assumption for unknown size
        return 0.6

    def _sum_weight_file_sizes(self, model_info: Dict[str, Any], include_all_candidates: bool = False) -> float:
        """Sum sizes (bytes) of files that look like model weights."""
        siblings = model_info.get("siblings") or []
        if not isinstance(siblings, list):
            return 0.0

        indicators = [
            ".safetensors",
            "pytorch_model.bin",
            "model.safetensors",
            "tf_model.h5",
            "model.onnx",
            ".gguf",
            "checkpoint",
        ]
        total_bytes = 0.0
        for file_info in siblings:
            if not isinstance(file_info, dict):
                continue
            name = str(
                file_info.get("rfilename")
                or file_info.get("filename")
                or file_info.get("path")
                or ""
            ).lower()
            if not name:
                continue
            if include_all_candidates or any(ind in name for ind in indicators):
                size_bytes = self._extract_file_size_bytes(file_info)
                if size_bytes > 0:
                    total_bytes += size_bytes
        return total_bytes

    def _extract_file_size_bytes(self, file_info: Dict[str, Any]) -> float:
        size_value = file_info.get("size")
        if size_value is None:
            lfs_info = file_info.get("lfs")
            if isinstance(lfs_info, dict):
                size_value = lfs_info.get("size")
        if size_value is None:
            return 0.0
        try:
            return float(size_value)
        except (TypeError, ValueError):
            return 0.0
    
    def calculate_latency(self) -> int:
        return getattr(self, '_latency', 0)


class LicenseMetric(Metric):
    """Evaluates license clarity and LGPL v2.1 compatibility"""
    
    def __init__(self) -> None:
        super().__init__()
        self.name = "license"
        self.weight = 0.125
        
        # LGPL v2.1 compatible licenses (higher scores)
        self.compatible_licenses = {
            "lgpl-2.1", "lgpl", "mit", "bsd", "apache-2.0", "apache license 2.0", "apache", "cc0-1.0"
        }
        
        # Problematic licenses (lower scores)  
        self.problematic_licenses = {
            "gpl", "gpl-3.0", "agpl", "cc-by-nc", "proprietary"
        }
    
    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        
        try:
            license_text = self._extract_license(model_info)
            
            score = self._score_license(license_text)
            self._latency = int((time.time() - start_time) * 1000)
            return score
            
        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0
    
    def _extract_license(self, model_info: Dict[str, Any]) -> str:
        """Extract license information from model data"""
        # Check various fields where license might be stored
        license_fields = ["license", "license_name", "license_type"]
        
        for field in license_fields:
            if field in model_info and model_info[field]:
                return str(model_info[field]).lower()
        
        # Check in tags or metadata
        if "tags" in model_info:
            for tag in model_info["tags"]:
                if "license:" in str(tag).lower():
                    return str(tag).lower().replace("license:", "").strip()

        # add logic to check model_info['readme] for a line with license: {license} in it
        if "readme" in model_info and model_info["readme"]:
            for line in model_info["readme"].split("\n"):
                if "license:" in line.lower():
                    return line.lower().replace("license:", "").strip()
        
        return ""
    
    def _score_license(self, license_text: str) -> float:
        """Score license based on compatibility and clarity"""
        if not license_text:
            return 0.0  # No license information
        
        license_lower = license_text.lower()
        
        # Check for compatible licenses
        for compatible in self.compatible_licenses:
            if compatible in license_lower:
                return 1.0  # High score for compatible licenses
        
        # Check for problematic licenses  
        for problematic in self.problematic_licenses:
            if problematic in license_lower:
                return 0.4  # Low score for incompatible licenses
        
        # Unknown license means most likely no license
        return 0.0
    
    def calculate_latency(self) -> int:
        return getattr(self, '_latency', 0)


class RampUpMetric(Metric):
    """Evaluates ease of getting started with the model"""
    
    def __init__(self) -> None:
        super().__init__()
        self.name = "ramp_up_time"
        self.weight = 0.125
    
    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        
        try:
            if isinstance(model_info, str):
                try:
                    model_info = json.loads(model_info)
                except Exception:
                    model_info = {}
            
            score = 0.0
            readme_text = model_info.get("readme", "")
            readme_present = bool((readme_text or "").strip())

            base_score = 0.0
            if readme_present:
                base_score += 0.20  # Adjusted from 0.15
            if model_info.get("description"):
                base_score += 0.07  # Adjusted from 0.05
            if model_info.get("tags"):
                base_score += 0.04  # Adjusted from 0.03
            score += min(0.30, base_score)  # Adjusted max from 0.25
            print(
                f"[RAMP_UP] Start metric={self.name} model_id={model_info.get('id')} "
                f"readme_present={readme_present} readme_length={len(readme_text or '')} "
                f"base_score={score:.3f}"
            )
            
            # Check for README quality (65% of score)
            readme_score = self._evaluate_readme(readme_text)
            score += readme_score * 0.50  # Reduced from 0.55
            
            # Check for clear model card/description (25% of score)
            card_score = self._evaluate_model_card(model_info)
            score += card_score * 0.25  # Reduced from 0.35
            
            self._latency = int((time.time() - start_time) * 1000)
            final_score = min(1.0, score)
            print(
                f"[RAMP_UP] Complete metric={self.name} model_id={model_info.get('id')} "
                f"readme_score={readme_score:.3f} card_score={card_score:.3f} "
                f"final_score={final_score:.3f} latency_ms={self._latency}"
            )
            return min(1.0, score)
            
        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            print(
                f"[RAMP_UP][ERROR] metric={self.name} model_id={model_info.get('id')} "
                f"latency_ms={self._latency} error={e}"
            )
            return 0.0
    
    def _evaluate_readme(self, readme: str) -> float:
        """Evaluate README quality"""
        if not readme:
            return 0.0
        
        readme_lower = readme.lower()
        score = 0.30  # Higher baseline - any README has value
        reasons: List[str] = ["baseline +0.30"]
        
        # Check for key sections - more generous scoring
        if "usage" in readme_lower or "how to use" in readme_lower:
            score += 0.25
            reasons.append("usage +0.25")
        if "example" in readme_lower or "```python" in readme_lower or "```" in readme_lower:
            score += 0.25
            reasons.append("examples +0.25")
        if "install" in readme_lower or "pip" in readme_lower:
            score += 0.15
            reasons.append("install +0.15")
        if any(term in readme_lower for term in ["quickstart", "getting started", "setup", "model"]):
            score += 0.10
            reasons.append("onboarding +0.10")
        if len(readme) > 200:
            score += 0.10
            reasons.append("length>200 +0.10")
        print(
            f"[RAMP_UP][README] reasons={reasons or ['none']} subtotal={min(1.0, score):.3f}"
        )
        
        return min(1.0, score)
    
    def _evaluate_model_card(self, model_info: Dict[str, Any]) -> float:
        """Evaluate model card completeness"""
        score = 0.0
        reasons: List[str] = []
        
        if model_info.get("description"):
            score += 0.7
            reasons.append("description +0.7")
        if model_info.get("datasets"):
            score += 0.2
            reasons.append("datasets +0.2")
        if model_info.get("tags"):
            score += 0.1  
            reasons.append("tags +0.1")
        print(
            f"[RAMP_UP][CARD] reasons={reasons or ['none']} subtotal={min(1.0, score):.3f}"
        )
        
        return min(1.0, score)
    
    def _evaluate_popularity(self, model_info: Dict[str, Any]) -> float:
        """Evaluate based on downloads and likes"""
        # Use safe defaults if fields are missing or None
        downloads_last_month = model_info.get("downloads_last_month") or 0
        likes = model_info.get("likes") or 0
        stars = model_info.get("stars") or 0

        # Normalize scores
        download_score = min(1.0, downloads_last_month / 10000)  # Scale to 10k downloads
        like_score = min(1.0, likes / 100)  # Scale to 100 likes
        stars_score = min(1.0, stars / 100)  # Scale to 100 stars

        return (download_score + like_score + stars_score) / 3
    
    def calculate_latency(self) -> int:
        return getattr(self, '_latency', 0)


class BusFactorMetric(Metric):
    """Evaluates knowledge concentration risk (higher = safer)"""
    
    def __init__(self) -> None:
        super().__init__()
        self.name = "bus_factor"
        self.weight = 0.125
    
    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        
        try:
            if isinstance(model_info, str):
                try:
                    model_info = json.loads(model_info)
                except Exception:
                    model_info = {}
            score = 0.2  # baseline trust that model is published and visible
            model_id = model_info.get("id")
            print(
                f"[BUS_FACTOR] Start metric={self.name} model_id={model_id} "
                f"author={model_info.get('author')} last_modified={model_info.get('lastModified')} "
                f"baseline_score={score:.3f}"
            )
            
            # Organization vs individual author (20% of score)
            org_score = self._evaluate_organization(model_info)
            score += org_score * 0.2
            
            # Number of collaborators/contributors (50% of score)
            contrib_score = self._evaluate_contributors(model_info)
            score += contrib_score * 0.5
            
            # Activity and maintenance (30% of score)
            activity_score = self._evaluate_activity(model_info)
            score += activity_score * 0.3
            
            self._latency = int((time.time() - start_time) * 1000)
            final_score = min(1.0, score)
            print(
                f"[BUS_FACTOR] Complete metric={self.name} model_id={model_id} "
                f"org_score={org_score:.3f} contrib_score={contrib_score:.3f} "
                f"activity_score={activity_score:.3f} final_score={final_score:.3f} "
                f"latency_ms={self._latency}"
            )
            return final_score
            
        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            print(
                f"[BUS_FACTOR][ERROR] metric={self.name} model_id={model_info.get('id')} "
                f"latency_ms={self._latency} error={e}"
            )
            return 0.0
    
    def _evaluate_organization(self, model_info: Dict[str, Any]) -> float:
        """Higher score for organizational backing"""
        author = model_info.get("author", "").lower()
        model_id = model_info.get("id", "").lower()
        reason = "individual"
        score = 0.5
        
        # Known organizations get higher scores
        organizations = [
            "google", "microsoft", "facebook", "meta", "openai", 
            "anthropic", "huggingface", "stanford", "mit", "berkeley",
            "research", "ai", "deepmind", "nvidia", "apple"
        ]
        
        # Check both author and model ID for organization indicators
        search_text = f"{author} {model_id}"
        for org in organizations:
            if org in search_text:
                reason = f"matched:{org}"
                score = 1.0
                break
        
        # Check if it looks like an organization (not individual name)
        if score < 1.0 and any(
            indicator in search_text
            for indicator in ["team", "lab", "corp", "inc", "ltd", "research", "ai", "institute"]
        ):
            reason = "org-indicator"
            score = 0.8
        print(
            f"[BUS_FACTOR][ORG] model_id={model_info.get('id')} score={score:.3f} reason={reason}"
        )
        return score
    
    def _evaluate_contributors(self, model_info: Dict[str, Any]) -> float:
        """Evaluate based on number of contributors"""
        # This would ideally use git metadata, simplified for now
        num_contributors = model_info.get("contributors_count") or 0

        # Ensure num_contributors is an int
        try:
            num_contributors = int(num_contributors)
        except Exception:
            num_contributors = 0

        if num_contributors >= 10:
            score = 1.0
        elif num_contributors >= 6:
            score = 0.8
        elif num_contributors >= 3:
            score = 0.6
        elif num_contributors >= 1:
            score = 0.4
        else:
            score = 0.3  # treat 0/unknown as low but not catastrophic
        print(
            f"[BUS_FACTOR][CONTRIB] model_id={model_info.get('id')} "
            f"contributors={num_contributors} score={score:.3f}"
        )
        return score
    
    def _evaluate_activity(self, model_info: Dict[str, Any]) -> float:
        """Evaluate recent activity based on last modified date"""
        last_modified = model_info.get("lastModified")
        if not last_modified:
            print(
                f"[BUS_FACTOR][ACTIVITY] model_id={model_info.get('id')} "
                f"reason=no_last_modified score=0.300"
            )
            return 0.3
        
        # Parse date and calculate days since last update
        try:
            last_date = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
            days_old = (datetime.now(timezone.utc) - last_date).days
            
            if days_old <= 30:
                score = 1.0
            elif days_old <= 90:
                score = 0.7
            elif days_old <= 365:
                score = 0.4
            else:
                score = 0.1
            print(
                f"[BUS_FACTOR][ACTIVITY] model_id={model_info.get('id')} days_old={days_old} "
                f"score={score:.3f}"
            )
            return score
        except:
            print(
                f"[BUS_FACTOR][ACTIVITY] model_id={model_info.get('id')} "
                f"reason=parse_error score=0.300"
            )
            return 0.3
    
    def calculate_latency(self) -> int:
        return getattr(self, '_latency', 0)


class AvailableScoreMetric(Metric):
    """Evaluates availability of dataset and code documentation"""
    
    def __init__(self) -> None:
        super().__init__()
        self.name = "dataset_and_code_score"
        self.weight = 0.125
    
    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        
        try:
            score = 0.0
            
            # Dataset documentation (50% of score)
            dataset_score = self._evaluate_dataset_info(model_info)
            score += dataset_score * 0.35  # More conservative
            
            # Code availability (50% of score)
            code_score = self._evaluate_code_availability(model_info)
            score += code_score * 0.35  # More conservative
            
            self._latency = int((time.time() - start_time) * 1000)
            return min(1.0, score)
            
        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0
    
    def _evaluate_dataset_info(self, model_info: Dict[str, Any]) -> float:
        """Evaluate dataset documentation quality"""
        score = 0.0
        
        # Check for dataset tags/metadata
        datasets = model_info.get("datasets")
        if datasets:
            score += 0.25  # Reduced from 0.3
        
        # Check README for dataset information
        readme = (model_info.get("readme") or "").lower()
        dataset_terms = ["dataset", "training data", "trained on", "corpus", "data", "pretraining", "fine-tuned", "benchmark"]
        if any(term in readme for term in dataset_terms):
            score += 0.15  # Reduced from 0.2
        
        # Check tags for dataset information
        tags = model_info.get("tags", [])
        dataset_tags = ["dataset", "corpus", "benchmark", "evaluation"]
        if any(any(tag_term in str(tag or "").lower() for tag_term in dataset_tags) for tag in tags):
            score += 0.15
        
        # Check for model card or description mentioning datasets
        description = (model_info.get("description") or "").lower()
        if description and any(term in description for term in dataset_terms):
            score += 0.2
        
        return min(1.0, score)
    
    def _evaluate_code_availability(self, model_info: Dict[str, Any]) -> float:
        """Evaluate code availability"""
        files = model_info.get("siblings", [])
        readme = (model_info.get("readme") or "").lower()

        score = 0.0
        
        # Check for actual code files
        if files:
            code_indicators = [".py", ".ipynb", ".js", ".ts", ".r", "train", "eval", "inference", "example", "demo", "config", ".json", ".yaml", ".yml", ".csv", ".txt", ".jsonl", ".jsonl.gz", ".jsonl.bz2", ".jsonl.xz", ".jsonl.zst", ".jsonl.lz4", ".jsonl.snappy", ".jsonl.gzip", ".jsonl.bzip2", ".jsonl.xz", ".jsonl.zst", ".jsonl.lz4", ".jsonl.snappy", ".jsonl.gzip", ".jsonl.bzip2", ".jsonl.xz", ".mlmodel"]
            
            for file_info in files:
                filename = str(file_info.get("rfilename") or "").lower()
                for indicator in code_indicators:
                    if indicator in filename:
                        score += 0.15
                        break
        
        # Check README for code examples or usage instructions
        code_terms = ["usage", "example", "code", "import", "from transformers", "model =", "tokenizer =", "```python", "```"]
        if any(term in readme for term in code_terms):
            score += 0.25
        
        # Check for model-specific files that indicate usability
        if files:
            model_files = ["config.json", "tokenizer", "vocab", "model.safetensors", "pytorch_model.bin"]
            for file_info in files:
                filename = str(file_info.get("rfilename") or "").lower()
                if any(model_file in filename for model_file in model_files):
                    score += 0.25
                    break
        
        # If no files but substantial documentation with usage info, still give some credit
        if not files and len(readme) > 500 and any(term in readme for term in ["usage", "how to use", "import"]):
            score = 0.3
        
        return min(1.0, score)
    
    def calculate_latency(self) -> int:
        return getattr(self, '_latency', 0)


class DatasetQualityMetric(Metric):
    """Evaluates quality of associated datasets"""
    
    def __init__(self) -> None:
        super().__init__()
        self.name = "dataset_quality"  
        self.weight = 0.125
    
    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        
        try:
            # Start with generous baseline - most ML models have some dataset
            score = 0.40
            readme = (model_info.get("readme") or "").lower()
            
            # Check for dataset mentions in README - simpler, higher scoring
            dataset_terms = ["training data", "dataset", "trained on", "fine-tuned", 
                           "corpus", "benchmark", "evaluation", "data"]
            
            term_matches = sum(1 for term in dataset_terms if term in readme)
            if term_matches >= 3:
                score += 0.30
            elif term_matches >= 1:
                score += 0.20
            
            # Check for dataset metadata
            datasets = model_info.get("datasets")
            if datasets:
                score += 0.20
            
            # Check description for dataset info
            description = (model_info.get("description") or "").lower()
            if description and any(term in description for term in dataset_terms):
                score += 0.15
            
            # Check tags for dataset information
            tags = model_info.get("tags", [])
            dataset_tags = ["dataset", "corpus", "benchmark", "evaluation"]
            if any(any(tag_term in str(tag or "").lower() for tag_term in dataset_tags) for tag in tags):
                score += 0.10
            
            self._latency = int((time.time() - start_time) * 1000)
            return min(1.0, score)
            
        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0
    
    def calculate_latency(self) -> int:
        return getattr(self, '_latency', 0)


class CodeQualityMetric(Metric):
    """Evaluates code style and maintainability"""
    
    def __init__(self) -> None:
        super().__init__()
        self.name = "code_quality"
        self.weight = 0.125
    
    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        
        try:
            # Start with generous baseline - most published models have usable code
            score = 0.45
            readme = (model_info.get("readme") or "").lower()
            
            # Check for code indicators in README - simpler scoring
            code_indicators = ["```", "import", "from", "model", "tokenizer", 
                             "usage", "example", "code", "load_model"]
            
            indicator_matches = sum(1 for indicator in code_indicators if indicator in readme)
            if indicator_matches >= 4:
                score += 0.30
            elif indicator_matches >= 2:
                score += 0.20
            
            # Check for actual model files
            files = model_info.get("siblings", [])
            if files:
                essential_files = ["config.json", ".safetensors", "pytorch_model", "tokenizer"]
                has_essential = any(
                    any(essential in str(f.get("rfilename") or "").lower() 
                        for essential in essential_files)
                    for f in files
                )
                if has_essential:
                    score += 0.20
            
            # Bonus for good documentation
            if len(readme) > 500:
                score += 0.10
            
            self._latency = int((time.time() - start_time) * 1000)
            return min(1.0, score)
            
        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0
    
    def calculate_latency(self) -> int:
        return getattr(self, '_latency', 0)


class PerformanceMetric(Metric):
    """Evaluates evidence of performance claims and benchmarks"""
    
    def __init__(self) -> None:
        super().__init__()
        self.name: str = "performance_claims"
        self.weight: float = 0.125
        self.system_prompt: str = self.get_system_prompt()

    def get_system_prompt(self) -> str:
        return """
You are an expert in evaluating machine learning model performance claims based on README content and available benchmark files.
Your task is to assess the credibility and quality of performance information provided for a given model.

When evaluating the README, look for:
- Explicit performance metrics (e.g. accuracy)
- Benchmark results
- Clear descriptions of evaluation methodology
- Numerical results that suggest actual benchmarking was performed
- Thorough explanation on how the model works and what it excels at

OUTPUT REQUIREMENTS:
- Start your response with the determined score and a newline character  (e.g. '0.85\\n')
- Return a float score between 0.0 and 1.0
- The float value should be the only content on the first line
- The float value should always be formatted to two decimal places
"""
    
    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        
        try:
            # Start conservative - performance claims should be well-documented
            readme = model_info.get("readme", "")
            readme_lower = readme.lower()
            
            # Quick heuristic check first
            performance_terms = ["accuracy", "benchmark", "evaluation", "metric", 
                               "performance", "score", "result"]
            has_metrics = any(term in readme_lower for term in performance_terms)
            
            if not has_metrics:
                score = 0.0  # No performance info at all
            else:
                # Have AI check README for performance metrics
                score = self._evaluate_performance_in_readme(readme)
                # Scale down AI score to be more conservative
                score = score * 0.75

            self._latency = int((time.time() - start_time) * 1000)
            return score
            
        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0
        
    def _evaluate_performance_in_readme(self, readme: str) -> float:
        try:
            # Initialize AWS Bedrock Runtime client
            bedrock_runtime = boto3.client(
                service_name='bedrock-runtime',
                region_name='us-east-1'
            )
            
            # Prepare the request body for Claude 3 Haiku
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": f"{self.system_prompt}\n\n{readme}"
                    }
                ]
            }
            
            # Invoke the model
            response = bedrock_runtime.invoke_model(
                modelId='anthropic.claude-3-haiku-20240307-v1:0',
                body=json.dumps(request_body)
            )
            
            # Parse the response
            response_body = json.loads(response['body'].read())
            
            # Extract the content from Claude's response
            content = response_body['content'][0]['text']
            
            # Parse the score from the first line
            # Require a trailing newline or explicit \n after the number (per test expectations)
            match = re.match(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:\n|\\n)', content)
            score: float = float(match.group(1)) if match else 0.0 

            return clamp(score, 0.0, 1.0)
            
        except Exception as e:
            print(f"Error calling AWS Bedrock: {str(e)}")
            return 0.0

    
    
    def calculate_latency(self) -> int:
        return getattr(self, '_latency', 0)
    
    
class ReproducibilityMetric(Metric):
    """
    Evaluates the reproducibility of model code snippets found in a README.

    Scoring:
        - 0.0 → No code or code does not run at all
        - 0.5 → Code fails due to minor, fixable issues (e.g., missing imports)
        - 1.0 → Code runs successfully without modification

    Implementation notes:
        • Extracts fenced code blocks (```python```).
        • Executes snippets safely in an isolated subprocess.
        • Logs detailed steps for traceability.
    """

    def __init__(self) -> None:
        super().__init__()
        self.name = "reproducibility"
        self.weight = 0.125
        self.debug_info: List[Dict[str, Any]] = []

    # ---------------------------------------------------------
    # Main evaluation entry point
    # ---------------------------------------------------------
    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        self.debug_info.clear()

        if isinstance(model_info, str):
            model_info = json.loads(model_info)

        readme = model_info.get("readme", "").strip()
        if not readme:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0

        snippets = self._extract_code_snippets(readme)

        if not snippets:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0

        best_score = 0.0
        for i, snippet in enumerate(snippets, start=1):
            score = self._evaluate_snippet(snippet, i)
            self.debug_info.append({"index": i, "score": score, "code": snippet})
            best_score = max(best_score, score)

            if best_score == 1.0:
                break

        self._latency = int((time.time() - start_time) * 1000)
        return best_score

    # ---------------------------------------------------------
    # Helper: extract fenced code blocks
    # ---------------------------------------------------------
    def _extract_code_snippets(self, readme: str) -> List[str]:
        """Extract runnable Python or bash-based snippets from README."""
        pattern = re.compile(r'```(python|py|bash|sh)?\s*(.*?)```',
                             re.DOTALL | re.IGNORECASE)
        matches = pattern.findall(readme)
        snippets = []

        for lang, code in matches:
            lang = (lang or "").lower()
            code = textwrap.dedent(code).strip()
            if lang in ["python", "py"]:
                snippets.append(code)
            else:
                pass  # Skipping non-Python snippet

        return snippets

    # ---------------------------------------------------------
    # Helper: execute and score snippet
    # ---------------------------------------------------------
    def _evaluate_snippet(self, snippet: str, index: int) -> float:
        """Safely execute a snippet and return a score based on outcome."""
        unsafe_patterns = [
            r'\bos\.system\b', r'\bos\.popen\b', r'\bsubprocess\b',
            r'\beval\b', r'\bexec\b', r'\bopen\b', r'\bsocket\b',
            r'\bthreading\b', r'\bmultiprocessing\b'
        ]
        for pattern in unsafe_patterns:
            if re.search(pattern, snippet):
                return 0.0

        with tempfile.TemporaryDirectory() as tmpdir:
            snippet_path = os.path.join(tmpdir, f"snippet_{index}.py")

            print(f"\n--- Snippet #{index} to be executed ---\n{snippet}\n--------------------------------------\n")

            with open(snippet_path, "w", encoding="utf-8") as f:
                f.write(snippet)

            env = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONNOUSERSITE": "1",
                "KMP_DUPLICATE_LIB_OK": "TRUE"  # prevents OMP duplicate errors
            }

            try:
                result = subprocess.run(
                    [sys.executable, snippet_path],
                    cwd=tmpdir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    text=True
                )

                stdout, stderr = result.stdout.strip(), result.stderr.strip()
                if stdout:
                    pass  # Snippet output present
                if stderr:
                    pass  # Snippet stderr present

                if result.returncode == 0:
                    return 1.0  # success

                # Check for fixable errors
                stderr_lower = stderr.lower()
                if any(err in stderr_lower for err in [
                    "importerror", "modulenotfounderror", "filenotfounderror",
                    "nameerror", "attributeerror"
                ]):
                    return 0.5

                return 0.0

            except subprocess.TimeoutExpired:
                return 0.5

    # ---------------------------------------------------------
    def calculate_latency(self) -> int:
        """Return the measured latency in milliseconds."""
        return getattr(self, "_latency", 0)



class ReviewedenessMetric(Metric):
    """Measures how much of the code was introduced via reviewed pull requests."""

    def __init__(self):
        super().__init__()
        self.name = "reviewedeness"
        self.weight = 0.05
        self._latency = 0

    def calculate_metric(self, model_info: Dict[str, Any]) -> float:
        start_time = time.time()
        try:
            repo_url = model_info.get("github_repo", "")
            if not repo_url:
                return -1.0  # per the spec, -1 if no repo linked

            reviewed_fraction = self._get_reviewed_fraction(repo_url)
            self._latency = int((time.time() - start_time) * 1000)
            return clamp(reviewed_fraction, 0.0, 1.0)

        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0

    def _get_reviewed_fraction(self, repo_url: str) -> float:
        """
        Fetch merged PRs and their review counts using the GitHub GraphQL API.
        Returns the fraction of merged PRs that had ≥1 review.
        """
        start_time = time.time()
        headers = {"Accept": "application/vnd.github+json"}
        token = os.getenv("TEAM18_GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            return 0.0

        # Extract owner/repo from URL
        m = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if not m:
            return 0.0
        owner, repo = m.group(1), m.group(2)

        # GraphQL query: latest 20 merged PRs + review counts
        query = f"""
        {{
        repository(owner: "{owner}", name: "{repo}") {{
            pullRequests(first: 20, states: MERGED, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{
            nodes {{
                number
                reviews {{ totalCount }}
            }}
            }}
        }}
        }}
        """
        url = "https://api.github.com/graphql"
        body = {"query": query}
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            prs = data.get("data", {}).get("repository", {}).get("pullRequests", {}).get("nodes", [])
            if not prs:
                return 0.0

            reviewed = sum(1 for pr in prs if pr.get("reviews", {}).get("totalCount", 0) > 0)
            fraction = reviewed / len(prs)
            self._latency = int((time.time() - start_time) * 1000)
            return fraction

        except Exception as e:
            self._latency = int((time.time() - start_time) * 1000)
            return 0.0

    def calculate_latency(self) -> int:
        return getattr(self, "_latency", 0)



def clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    """
    Clip a float between min and max limits
    
    Why? Performance is faster than `numpy.clip()` and more readable than `min(max())`
    """
    if value < min_value: return min_value
    if value > max_value: return max_value
    return value
