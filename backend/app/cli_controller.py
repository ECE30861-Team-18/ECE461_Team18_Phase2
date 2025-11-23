"""
CLI Controller
Handles command line interface and orchestrates application flow.
"""

import re # regex
import sys # command line argument parsing
import os # env var access
import argparse # command-line parsing
from datetime import datetime # timestamp handling
import logging # logging system implementation
import subprocess # pip install and pytest commands
import json # output model scores
from pathlib import Path # filepath handling
from typing import List, Dict, Any, Optional # type annotations
from url_handler import URLHandler # URL_HANDLER
from url_category import URLCategory # URL_CATEGORY
from url_data import URLData, RepositoryData # URL_DATA
from data_retrieval import DataRetriever # DATA_RETRIEVER
from metric_calculator import MetricCalculator # METRIC_CALCULATOR
try:
    from dotenv import load_dotenv # pyright: ignore[reportMissingImports]
    # Load .env and allow values in .env to override existing environment variables
    # (this is important because the `run` script may export empty defaults).
    load_dotenv(override=True)
except Exception:
    # If python-dotenv is not installed, proceed without loading .env
    pass

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logger.info("cli_controller initialized")

HF_TOKEN = os.environ.get('HF_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')


class CLIController:
    """
    Main CLI controller implementation, orchestrates application flow.
    """
    
    def __init__(self) -> None:
        """ 
        Initialize CLI controller w/ logging and basic setup.
        """
        self.url_handler: URLHandler = URLHandler()
        self.metric_calculator: MetricCalculator = MetricCalculator()
        self.data_retriever = DataRetriever(github_token=GITHUB_TOKEN, hf_token=HF_TOKEN)
        self.valid_url_categories = {URLCategory.GITHUB, URLCategory.NPM, URLCategory.HUGGINGFACE}
        # if not self.check_github_token_validity():
        #     sys.exit(1)

    # def _ensure_github_token(self) -> bool:
    #     """
    #     Ensure the GitHub token is present and valid. Returns True when valid.
    #     This is a runtime check and should not call sys.exit so unit tests can
    #     import the module without side effects.
    #     """
    #     if not check_github_token_validity():
    #         logger.error("Invalid GitHub Token passed.")
    #         return False
    #     return True

    def parse_arguments(self) -> argparse.Namespace:
        """
        Parse command line arguments.
        Supports: install, URL_FILE, and test commands.
        """

        parser = argparse.ArgumentParser(
            description="ACME Corp Trustworthy Model Tool",
            prog="run"
        )

        parser.add_argument(
            'command',
            help='Command to execute: install, test, or path to URL file'
        )

        return parser.parse_args()
    
    def install_dependencies(self) -> int:
        """
        Install dependencies using pip install --user.

        Returns: 0 for success, 1 for failure
        """

        logger.info("Installing dependencies.")

        try:
            # Use the current Python executable to run pip to avoid relying on a 'pip'
            # binary on PATH which may not exist in some environments.
            result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '--user'],
                    capture_output=True,
                    text=True,
                    timeout=300 # 5 min timeout
                )


            if result.returncode != 0:
                    logger.error(f"Error installing required packages.: {result.stderr}")
                    return 1
                
            logger.info("Installed all dependencies successfully.")
            return 0
        
        except Exception as e:
            print(f"Error during installation: {str(e)}", file=sys.stderr)
            return 1


    def process_single_model(self, data: Dict[str, Optional[URLData]]) -> Optional[Dict[str, Any]]:
        """
        Process a single model's URLs and calculate its metrics.
        Then format as NDJSON to return.
        
        Returns: Dict of metrics : (scores, latencies) | None
        """
        try:
            code_repo = None
            dataset_repo = None
            model_repo = None

            if data.get('code'):
                code_repo = self.data_retriever.retrieve_data(data['code'])
            if data.get('dataset'):
                dataset_repo = self.data_retriever.retrieve_data(data['dataset'])
            if data.get('model'):
                model_repo = self.data_retriever.retrieve_data(data['model'])

            code_dict = self._normalize_repo(code_repo)
            dataset_dict = self._normalize_repo(dataset_repo)
            model_dict = self._normalize_repo(model_repo)

            # Build union of keys
            keys = set(code_dict.keys()) | set(dataset_dict.keys()) | set(model_dict.keys())

            merged: Dict[str, Any] = {}
            for key in keys:
                # precedence: model > dataset > code, prefer non-None values
                val = None
                if key in model_dict and model_dict.get(key) is not None:
                    val = model_dict.get(key)
                elif key in dataset_dict and dataset_dict.get(key) is not None:
                    val = dataset_dict.get(key)
                elif key in code_dict:
                    val = code_dict.get(key)
                else:
                    val = None
                merged[key] = val

            merged['code_present'] = False if code_repo is None else True
            merged['dataset_present'] = False if dataset_repo is None else True
            # print(merged['code_present'])
            # print(merged['dataset_present'])
            # call metric calculator - pass the merged dict directly (calculator expects a dict)
            metric_results = self.metric_calculator.calculate_all_metrics(merged, "MODEL")
            metric_results['name'] = model_dict['name']
            return metric_results

        except Exception as e:
            logger.error(f"Error processing model data: {str(e)}")
            print(f"Error processing model data: {str(e)}")
            return None

    def _normalize_repo(self, repo: Any) -> Dict[str, Any]:
        """
        Merge RepositoryData objects from model, dataset, and code into a single dict
        with precedence model > dataset > code. Accepts RepositoryData instances or dicts.
        """
        if repo is None:
            return {}

        if isinstance(repo, dict):
            result = dict(repo)
        else:
            # Fallback: try to read attributes
            result = {}
            for attr in dir(repo):
                if not attr.startswith('_') and not callable(getattr(repo, attr)):
                    try:
                        result[attr] = getattr(repo, attr)
                    except Exception:
                        continue

        # Convert datetime objects to ISO strings for portability
        for k, v in list(result.items()):
            try:
                if isinstance(v, datetime):
                    result[k] = v.isoformat()
            except Exception:
                continue
        return result

    def process_urls(self, url_file_path: str) -> int:
        """
        Process all URLs from file and output NDJSON results.

        Returns: 0 on success, 1 on failure.
        """

        try:
            urls = self.url_handler.read_urls_from_file(url_file_path)

            valid_objs = []
            for url in urls:
                try:
                    code_data = self.url_handler.handle_url(url['code'])
                    dataset_data = self.url_handler.handle_url(url['dataset'])
                    model_data = self.url_handler.handle_url(url['model'])
                    if model_data.is_valid and model_data.category in self.valid_url_categories:
                        valid = {}
                        valid['code'] = code_data if code_data.is_valid and code_data.category in self.valid_url_categories else None
                        valid['dataset'] = dataset_data if dataset_data.is_valid and dataset_data.category in self.valid_url_categories else None
                        valid['model'] = model_data
                        valid_objs.append(valid)
                except Exception:
                    continue

            # valid_objs = list[dicts with keys 'code', 'dataset', 'model']
            logger.info(f"Processing {len(valid_objs)} models.")

            for obj in valid_objs:
                result = self.process_single_model(obj) # TODO: IMPLEMENT THIS METHOD 
                if result:
                    # # write output to NDJSON file for debugging purposes
                    # with open('output.ndjson', 'a') as f:
                    #     f.write(json.dumps(result) + '\n')
                    print(json.dumps(result))
                    sys.stdout.flush()

            return 0
        
        except Exception as e:
            print(f"Error processing URLs: {str(e)}", file=sys.stderr)
            return 1

    def run_tests(self) -> int:
        """
        Run test suite using pytest.

        Returns: 0 for success, 1 for failure
        """

        logger.info("Executing tests.")

        try:

            # Use the current Python executable to run pytest so we don't depend on a
            # 'python' binary on PATH. This ensures consistent interpreter usage.
            result = subprocess.run([
                sys.executable, '-m', 'pytest',
                '--cov=app',
                '--cov-report=term-missing',
                '--tb=short',
                '-v',
                './tests'
            ], capture_output=True, text=True, timeout=300) # 5 min timeout

            # parse results
            lines = result.stdout.split('\n')
            test_line = ''
            coverage_line = ''

            for line in lines:
                if "passed" in line or "failed" in line:
                    test_line = line
                elif "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for part in parts:
                        if "%" in part:
                            coverage_line = part.replace("%", "")
                            break
            if not test_line or not coverage_line:
                passed = 0
                failed = 0
                coverage = 0

                # if result.returncode == 0: # this is problematic
                #     passed = 20
                #     failed = 0
                #     coverage = 80
            else:
                nums = re.findall(r'\d+', test_line)
                if len(nums) >= 2:
                    passed = int(nums[0]) if "passed" in test_line else 0
                    failed = int(nums[1]) if "failed" in test_line else 0
                else:
                    passed = 0
                    failed = 0
                try:
                    coverage = int(float(coverage_line))
                except (ValueError, TypeError):
                    coverage = 0

            total_tests = passed + failed

            # output test results
            print(f"{passed}/{total_tests} test cases passed. {coverage}% line coverage achieved.")

            logger.info(f"Test execution completed: {passed}/{total_tests} passed, {coverage}% coverage")

            return result.returncode
        
        except subprocess.TimeoutExpired:
            print("Error: timeout exceeded", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            return 1

        
    def run(self) -> int:
        """
        Entry point for CLI controller.
        
        Returns: Exit code (0 for success, 1 for failure).
        """

        try:
            args = self.parse_arguments()
            command = args.command

            logger.info(f"Executing command: {command}")

            if command == 'install':
                return self.install_dependencies()
            elif command == 'test':
                # Running tests does not need a GitHub token; don't validate here.
                return self.run_tests()
            else:
                return self.process_urls(command)
        
        except KeyboardInterrupt:
            print("Operation interrupted by user", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {str(e)}")
            logger.error(f"Error: {str(e)}")
            return 1
