import os
import requests
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json
import base64
import logging

# from url_handler import URLData, URLCategory
from url_data import URLData, RepositoryData
from url_category import URLCategory

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logger.info("data_retrieval initialized")


class GitHubAPIClient:
    def __init__(self, token: Optional[str] = None):
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        
        if token:
            self.session.headers.update({"Authorization": f"token {token}"})
        
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ECE461-Package-Analyzer"
        })
    
    def get_repository_data(self, owner: str, repo: str) -> RepositoryData:
        try:
            # Get basic repository information
            repo_url = f"{self.base_url}/repos/{owner}/{repo}"
            logger.info("GitHubAPIClient: requesting repo %s/%s", owner, repo)
            response = self.session.get(repo_url)
            
            if response.status_code == 404:
                logger.warning("GitHubAPIClient: repository not found %s/%s", owner, repo)
                return RepositoryData(
                    platform="github",
                    identifier=f"{owner}/{repo}",
                    name=repo,
                    success=False,
                    error_message="Repository not found"
                )
            elif response.status_code == 403:
                logger.warning("GitHubAPIClient: rate limited when accessing %s/%s", owner, repo)
                return RepositoryData(
                    platform="github",
                    identifier=f"{owner}/{repo}",
                    name=repo,
                    success=False,
                    error_message="Rate limit exceeded"
                )
            
            response.raise_for_status()
            repo_data = response.json()
            
            # Get contributors count (separate API call)
            contributors_count = self._get_contributors_count(owner, repo)
            logger.debug("GitHubAPIClient: contributors_count=%s for %s/%s", contributors_count, owner, repo)
            
            # Parse dates
            created_at = None
            updated_at = None
            if repo_data.get('created_at'):
                created_at = datetime.fromisoformat(repo_data['created_at'].replace('Z', '+00:00'))
            if repo_data.get('updated_at'):
                updated_at = datetime.fromisoformat(repo_data['updated_at'].replace('Z', '+00:00'))
            
            # Attempt to fetch README as raw text
            readme = None
            try:
                readme_url = f"{self.base_url}/repos/{owner}/{repo}/readme"
                # Prefer raw content when possible
                r = self.session.get(readme_url, headers={"Accept": "application/vnd.github.v3.raw"}, timeout=10)
                if r.status_code == 200:
                    readme = r.text
                else:
                    r2 = self.session.get(readme_url, timeout=10)
                    if r2.status_code == 200:
                        j = r2.json()
                        content_b64 = j.get("content")
                        encoding = j.get("encoding", "")
                        if content_b64 and encoding == "base64":
                            try:
                                readme = base64.b64decode(content_b64).decode("utf-8", errors="replace")
                            except Exception:
                                readme = None
            except Exception:
                logger.exception("GitHubAPIClient: failed to fetch README for %s/%s", owner, repo)
                readme = None

            return RepositoryData(
                platform="github",
                identifier=f"{owner}/{repo}",
                name=repo_data.get('name', repo),
                description=repo_data.get('description'),
                stars=repo_data.get('stargazers_count', 0),
                forks=repo_data.get('forks_count', 0),
                watchers=repo_data.get('watchers_count', 0),
                issues_count=repo_data.get('open_issues_count', 0),
                contributors_count=contributors_count,
                language=repo_data.get('language'),
                license=repo_data.get('license', {}).get('name') if repo_data.get('license') else None,
                created_at=created_at,
                updated_at=updated_at,
                homepage=repo_data.get('homepage'),
                repository_url=repo_data.get('html_url'),
                success=True,
                readme=readme,
            )
            
        except requests.exceptions.RequestException as e:
            logger.exception("GitHubAPIClient: request exception for %s/%s", owner, repo)
            return RepositoryData(
                platform="github",
                identifier=f"{owner}/{repo}",
                name=repo,
                success=False,
                error_message=f"API request failed: {str(e)}"
            )
        except Exception as e:
            logger.exception("GitHubAPIClient: unexpected error for %s/%s", owner, repo)
            return RepositoryData(
                platform="github",
                identifier=f"{owner}/{repo}",
                name=repo,
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def _get_contributors_count(self, owner: str, repo: str) -> Optional[int]:
        try:
            contributors_url = f"{self.base_url}/repos/{owner}/{repo}/contributors"
            logger.debug("GitHubAPIClient: requesting contributors for %s/%s", owner, repo)
            response = self.session.get(contributors_url, params={"per_page": 1})
            
            if response.status_code == 200:
                # Check if there's a Link header for pagination
                link_header = response.headers.get('Link', '')
                if 'rel="last"' in link_header:
                    # Extract page count from last page link
                    import re
                    last_page_match = re.search(r'page=(\d+)>; rel="last"', link_header)
                    if last_page_match:
                        return int(last_page_match.group(1))
                
                # If no pagination, count current page
                contributors = response.json()
                count = len(contributors) if contributors else 0
                logger.debug("GitHubAPIClient: contributors count (no pagination) = %d for %s/%s", count, owner, repo)
                return count
            
            return None
        except:
            logger.exception("GitHubAPIClient: failed to get contributors for %s/%s", owner, repo)
            return None


class NPMAPIClient:
    def __init__(self):
        """Initialize NPM API client."""
        self.base_url = "https://registry.npmjs.org"
        self.downloads_url = "https://api.npmjs.org/downloads"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ECE461-Package-Analyzer"
        })
    
    def get_package_data(self, package_name: str) -> RepositoryData:
        try:
            # Get package information
            package_url = f"{self.base_url}/{package_name}"
            logger.info("NPMAPIClient: requesting package %s", package_name)
            response = self.session.get(package_url)
            
            if response.status_code == 404:
                logger.warning("NPMAPIClient: package not found %s", package_name)
                return RepositoryData(
                    platform="npm",
                    identifier=package_name,
                    name=package_name,
                    success=False,
                    error_message="Package not found"
                )
            
            response.raise_for_status()
            package_data = response.json()
            
            # Get download statistics
            downloads_last_month = self._get_download_count(package_name)
            logger.debug("NPMAPIClient: downloads_last_month=%s for %s", downloads_last_month, package_name)
            
            # Extract latest version data
            latest_version = package_data.get('dist-tags', {}).get('latest', '')
            version_data = package_data.get('versions', {}).get(latest_version, {})
            
            # Parse dependencies
            dependencies = list(version_data.get('dependencies', {}).keys())
            dev_dependencies = list(version_data.get('devDependencies', {}).keys())
            
            # Parse dates
            created_at = None
            updated_at = None
            time_data = package_data.get('time', {})
            if time_data.get('created'):
                created_at = datetime.fromisoformat(time_data['created'].replace('Z', '+00:00'))
            if time_data.get('modified'):
                updated_at = datetime.fromisoformat(time_data['modified'].replace('Z', '+00:00'))
            
            # Extract repository URL if available
            repository_info = version_data.get('repository', {})
            repository_url = None
            if isinstance(repository_info, dict):
                repository_url = repository_info.get('url', '').replace('git+', '').replace('.git', '')

            # Attempt to get README from registry or from repository
            readme = None
            try:
                readme = package_data.get('readme')
                if not readme and repository_url and 'github.com' in repository_url:
                    import re
                    m = re.search(r"github[./:]+([^/]+)/([^/]+)(?:\.git)?", repository_url)
                    if m:
                        owner = m.group(1)
                        repo_name = m.group(2)
                        # try common branches
                        for branch in ("main", "master"):
                            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/README.md"
                            rr = self.session.get(raw_url, timeout=10)
                            if rr.status_code == 200 and rr.text.strip():
                                readme = rr.text
                                break
            except Exception:
                logger.exception("NPMAPIClient: failed to fetch README for %s", package_name)
                readme = None

            return RepositoryData(
                platform="npm",
                identifier=package_name,
                name=package_data.get('name', package_name),
                description=version_data.get('description', package_data.get('description')),
                version=latest_version,
                downloads_last_month=downloads_last_month,
                dependencies=dependencies,
                dev_dependencies=dev_dependencies,
                created_at=created_at,
                updated_at=updated_at,
                homepage=version_data.get('homepage'),
                repository_url=repository_url,
                license=version_data.get('license'),
                success=True,
                readme=readme,
            )
            
        except requests.exceptions.RequestException as e:
            logger.exception("NPMAPIClient: request exception for package %s", package_name)
            return RepositoryData(
                platform="npm",
                identifier=package_name,
                name=package_name,
                success=False,
                error_message=f"API request failed: {str(e)}"
            )
        except Exception as e:
            logger.exception("NPMAPIClient: unexpected error for package %s", package_name)
            return RepositoryData(
                platform="npm",
                identifier=package_name,
                name=package_name,
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def _get_download_count(self, package_name: str) -> Optional[int]:
        try:
            downloads_url = f"{self.downloads_url}/point/last-month/{package_name}"
            logger.debug("NPMAPIClient: requesting download stats for %s", package_name)
            response = self.session.get(downloads_url)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('downloads', 0)
            
            return None
        except:
            logger.exception("NPMAPIClient: failed to fetch download stats for %s", package_name)
            return None


class HuggingFaceAPIClient:
    def __init__(self, token: Optional[str] = None):
        # Avoid printing the raw token to stdout/stderr. Log whether a token was
        # provided (without revealing it) to help with debugging token-loading.
        logger.debug("HuggingFaceAPIClient: HF token provided=%s", bool(token))
        self.base_url = "https://huggingface.co/api"
        self.session = requests.Session()
        # Only set Authorization header when a non-empty token is provided.
        # Passing an empty string or None previously resulted in an Authorization
        # header like 'Bearer ' or 'Bearer None', which caused 401 Unauthorized
        # responses from the Hugging Face API for otherwise-public resources.
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.session.headers.update({
            "User-Agent": "ECE461-Package-Analyzer"
        })
    
    def _extract_license_from_readme(self, readme: str) -> Optional[str]:
        """
        Extract license from YAML frontmatter in README.
        Looks for a block like:
        ---
        license: apache-2.0
        ---
        """
        if not readme:
            return None
        
        try:
            # Check if README starts with YAML frontmatter (---)
            if not readme.strip().startswith('---'):
                return None
            
            # Find the closing --- of the frontmatter
            lines = readme.split('\n')
            frontmatter_end = -1
            for i in range(1, len(lines)):
                if lines[i].strip() == '---':
                    frontmatter_end = i
                    break
            
            if frontmatter_end == -1:
                return None
            
            # Parse the frontmatter lines
            frontmatter = '\n'.join(lines[1:frontmatter_end])
            
            # Look for license field
            import re
            license_match = re.search(r'^license:\s*(.+)$', frontmatter, re.MULTILINE | re.IGNORECASE)
            if license_match:
                license_value = license_match.group(1).strip()
                logger.debug("HuggingFaceAPIClient: extracted license from README: %s", license_value)
                return license_value
            
            return None
        except Exception as e:
            logger.exception("HuggingFaceAPIClient: error extracting license from README")
            return None
    
    def get_model_data(self, identifier: str) -> RepositoryData:
        try:
            # Try to get model information first
            model_url = f"{self.base_url}/models/{identifier}"
            logger.info("HuggingFaceAPIClient: requesting model/dataset %s", identifier)
            response = self.session.get(model_url, params={"expand": "files"})
            
            if response.status_code == 404:
                # Try as dataset
                dataset_url = f"{self.base_url}/datasets/{identifier}"
                response = self.session.get(dataset_url, params={"expand": "files"})
                
                if response.status_code == 404:
                    logger.warning("HuggingFaceAPIClient: model/dataset not found %s", identifier)
                    return RepositoryData(
                        platform="huggingface",
                        identifier=identifier,
                        name=identifier.split('/')[-1],
                        success=False,
                        error_message="Model/dataset not found"
                    )
            
            response.raise_for_status()
            model_data = response.json()
            logger.debug("HuggingFaceAPIClient: received data for %s, keys=%s", identifier, list(model_data.keys()))
            
            # Parse dates
            created_at = None
            updated_at = None
            if model_data.get('createdAt'):
                created_at = datetime.fromisoformat(model_data['createdAt'].replace('Z', '+00:00'))
            if model_data.get('lastModified'):
                updated_at = datetime.fromisoformat(model_data['lastModified'].replace('Z', '+00:00'))
            # Attempt to obtain README / model card content
            readme = None
            try:
                # check common fields in model_data
                if isinstance(model_data, dict):
                    # many HF responses include 'cardData' or 'readme'
                    readme = model_data.get('readme') or model_data.get('cardData') or model_data.get('modelCard')
                    if isinstance(readme, dict):
                        # cardData may contain 'body' or 'content'
                        readme = readme.get('body') or readme.get('content') or None
                # fallback to raw README URL
                if not readme:
                    raw_url = f"https://huggingface.co/{identifier}/raw/main/README.md"
                    r = self.session.get(raw_url, timeout=10)
                    if r.status_code == 200:
                        readme = r.text
            except Exception:
                logger.exception("HuggingFaceAPIClient: failed to fetch README for %s", identifier)
                readme = None

            # Extract license from README frontmatter if available
            extracted_license = self._extract_license_from_readme(readme) if readme else None
            final_license = extracted_license or model_data.get('license')

            return RepositoryData(
                platform="huggingface",
                identifier=identifier,
                name=model_data.get('id', identifier).split('/')[-1],
                description=model_data.get('description'),
                downloads_last_month=model_data.get('downloads', 0),
                created_at=created_at,
                updated_at=updated_at,
                language=model_data.get('pipeline_tag'),  # Using pipeline_tag as language equivalent
                license=final_license,
                repository_url=f"https://huggingface.co/{identifier}",
                success=True,
                readme=readme,
                # Additional HuggingFace fields
                author=model_data.get('author'),
                sha=model_data.get('sha'),
                last_modified=model_data.get('lastModified'),
                private=model_data.get('private'),
                gated=model_data.get('gated'),
                disabled=model_data.get('disabled'),
                tags=model_data.get('tags'),
                citation=model_data.get('citation'),
                paperswithcode_id=model_data.get('paperswithcode_id'),
                downloads=model_data.get('downloads'),
                likes=model_data.get('likes'),
                card_data=str(model_data.get('cardData')) if model_data.get('cardData') else None,
                used_storage=model_data.get('usedStorage'),
                pipeline_tag=model_data.get('pipeline_tag'),
                library_name=model_data.get('library_name'),
                model_id=model_data.get('modelId'),
                mask_token=model_data.get('mask_token'),
                widget_data=str(model_data.get('widgetData')) if model_data.get('widgetData') else None,
                model_index=str(model_data.get('model-index')) if model_data.get('model-index') else None,
                config=str(model_data.get('config')) if model_data.get('config') else None,
                transformers_info=str(model_data.get('transformersInfo')) if model_data.get('transformersInfo') else None,
                spaces=model_data.get('spaces'),
                safetensors=model_data.get('safetensors'),
                inference=model_data.get('inference'),
                siblings=model_data.get('siblings'),
            )
            
        except requests.exceptions.RequestException as e:
            logger.exception("HuggingFaceAPIClient: request exception for %s", identifier)
            return RepositoryData(
                platform="huggingface",
                identifier=identifier,
                name=identifier.split('/')[-1],
                success=False,
                error_message=f"API request failed: {str(e)}"
            )
        except Exception as e:
            logger.exception("HuggingFaceAPIClient: unexpected error for %s", identifier)
            return RepositoryData(
                platform="huggingface",
                identifier=identifier,
                name=identifier.split('/')[-1],
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )


class DataRetriever:
    def __init__(self, github_token: Optional[str] = None, hf_token: Optional[str] = None, rate_limit_delay: float = 0.1):
        self.github_client = GitHubAPIClient(github_token)
        self.npm_client = NPMAPIClient()
        self.huggingface_client = HuggingFaceAPIClient(hf_token)
        self.rate_limit_delay = rate_limit_delay
        logger.info("DataRetriever initialized (rate_limit_delay=%s)", rate_limit_delay)
    
    def retrieve_data(self, url_data: Optional[URLData]) -> RepositoryData:
        if not url_data or not url_data.is_valid or not url_data.unique_identifier:
            logger.warning("DataRetriever.retrieve_data: invalid URLData provided: %s", url_data)
            return RepositoryData(
                platform="unknown", #url_data.category.value,
                identifier="unknown", #url_data.unique_identifier or 
                name="unknown",
                success=False,
                error_message="Invalid URL data provided"
            )
        
        # Add rate limiting delay
        logger.debug("DataRetriever.retrieve_data: sleeping for rate limit %s seconds", self.rate_limit_delay)
        time.sleep(self.rate_limit_delay)
        
        if url_data.category == URLCategory.GITHUB:
            owner = url_data.owner
            repo = url_data.repository
            if owner is None or repo is None:
                logger.warning("DataRetriever.retrieve_data: missing owner/repo for GitHub URLData: %s", url_data)
                return RepositoryData(
                    platform="github",
                    identifier=url_data.unique_identifier or "unknown",
                    name=repo or "unknown",
                    success=False,
                    error_message="Missing owner or repository for GitHub URL"
                )
            logger.info("DataRetriever: fetching GitHub repo data for %s/%s", owner, repo)
            return self.github_client.get_repository_data(owner, repo)
        elif url_data.category == URLCategory.NPM:
            package_name = url_data.package_name
            if package_name is None:
                logger.warning("DataRetriever.retrieve_data: missing package_name for NPM URLData: %s", url_data)
                return RepositoryData(
                    platform="npm",
                    identifier=url_data.unique_identifier or "unknown",
                    name="unknown",
                    success=False,
                    error_message="Missing package name for NPM URL"
                )
            logger.info("DataRetriever: fetching NPM package data for %s", package_name)
            return self.npm_client.get_package_data(package_name)
        elif url_data.category == URLCategory.HUGGINGFACE:
            identifier = url_data.unique_identifier
            if identifier is None:
                logger.warning("DataRetriever.retrieve_data: missing identifier for HuggingFace URLData: %s", url_data)
                return RepositoryData(
                    platform="huggingface",
                    identifier="unknown",
                    name="unknown",
                    success=False,
                    error_message="Missing identifier for Hugging Face URL"
                )
            logger.info("DataRetriever: fetching Hugging Face model data for %s", identifier)
            return self.huggingface_client.get_model_data(identifier)
        elif url_data.category == URLCategory.KAGGLE:
            identifier = url_data.unique_identifier or "unknown"
            name = identifier.split('/')[-1] if '/' in identifier else identifier
            logger.info("DataRetriever: Kaggle dataset %s (stub data)", identifier)
            # Return basic stub data for Kaggle - we don't call their API
            return RepositoryData(
                platform="kaggle",
                identifier=identifier,
                name=name,
                description="Kaggle dataset",
                success=True
            )
        else:
            identifier = url_data.unique_identifier or "unknown"
            name = identifier.split('/')[-1] if '/' in identifier else identifier
            logger.warning("DataRetriever.retrieve_data: unsupported platform %s", url_data.category)
            return RepositoryData(
                platform="unknown",
                identifier=identifier,
                name=name,
                success=False,
                error_message=f"Unsupported platform"
            )
    
    def retrieve_batch_data(self, url_data_list: List[URLData]) -> List[RepositoryData]:
        results = []
        
        for i, url_data in enumerate(url_data_list):
            logger.info("retrieve_batch_data: retrieving %d/%d - %s", i+1, len(url_data_list), url_data.unique_identifier)
            result = self.retrieve_data(url_data)
            logger.debug("retrieve_batch_data: result for %s: success=%s", url_data.unique_identifier, result.success)
            results.append(result)
        
        return results

