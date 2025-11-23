import warnings
import sys
import os
import argparse
from pathlib import Path
import logging
import requests
try:
    from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]
    # Load .env from the app directory since main.py is run from project root
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True) 
except Exception:
    # dotenv is optional for running tests; absence should not break execution
    pass

# Suppress noisy RequestsDependencyWarning emitted by system-installed requests
# when urllib3/chardet versions are different than expected. Do this before
# importing any module that may import `requests`.
warnings.filterwarnings("ignore", module=r"requests.*")

# NOTE: We intentionally do NOT import CLIController at module import time.
# Tests patch `app.main.CLIController`, so we keep a module attribute that can
# be patched while avoiding side effects before env validation.
CLIController = None  # type: ignore


def _validate_log_path_from_env() -> None:
    """
    No-op for AWS Lambda/ECS: file-based logging paths are ignored.
    """
    return


def _configure_logging_from_env() -> None:
    """
    Configure root logger to stdout with verbosity from LOG_LEVEL.
    LOG_LEVEL: 0 -> silent, 1 -> INFO, 2 -> DEBUG. Default is 0 (silent).
    """
    # Determine verbosity
    try:
        level_env = int(os.environ.get('LOG_LEVEL', '0'))
    except Exception:
        level_env = 0

    if level_env <= 0:
        level = logging.CRITICAL + 10  # effectively silent
    elif level_env == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    # Configure logging to stdout only
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger().setLevel(level)
    # Emit a minimal confirmation message at the configured verbosity so
    # downstream checks can verify that logging is active at this level.
    try:
        if level_env >= 2:
            logging.debug("Logging configured at DEBUG (LOG_LEVEL=2)")
        if level_env >= 1:
            logging.info("Logging configured at INFO (LOG_LEVEL=1)")
    except Exception:
        # Don't fail the program if writing the confirmation log line fails
        pass


def _parse_commandline_for_preflight(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('command', nargs='?')
    try:
        args, _ = parser.parse_known_args(argv[1:])
        return args.command or ''
    except SystemExit:
        # If parsing fails (e.g., unknown args), skip token validation
        return ''


def _validate_github_token_if_required(command: str) -> None:
    """
    For commands other than 'install' and 'test', require a non-empty GITHUB_TOKEN.
    Exit 1 if invalid or missing.
    """
    # Only enforce when a concrete command is provided and it's not install/test
    if command in ('', 'install', 'test'):
        return
    token = os.environ.get('GITHUB_TOKEN')
    if not token or not token.strip():
        print("Error: Invalid or missing GITHUB_TOKEN in environment.", file=sys.stderr)
        sys.exit(1)

    # Perform a lightweight validation against GitHub API; tests may mock requests.get
    try:
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        resp = requests.get('https://api.github.com/user', headers=headers, timeout=5)
        if resp.status_code != 200:
            print(f"Error: GitHub token invalid or lacks permissions. Status code: {resp.status_code}", file=sys.stderr)
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: could not validate GitHub token: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    # Preflight env validation before importing the rest of the application
    _validate_log_path_from_env()
    # Configure logging per environment after validating the path
    _configure_logging_from_env()
    command = _parse_commandline_for_preflight(sys.argv)
    _validate_github_token_if_required(command)

    global CLIController  # patched by tests
    if CLIController is None:
        # Import lazily after preflight checks
        from cli_controller import CLIController as _RealCLIController
        CLIController = _RealCLIController

    controller = CLIController()
    exit_code = controller.run()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()