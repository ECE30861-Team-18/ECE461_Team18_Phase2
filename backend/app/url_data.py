"""
Dataclasses containing information about a URL or a repository
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Any
from url_category import URLCategory

@dataclass
class URLData:
    original_url: str
    category: Optional[URLCategory]
    hostname: str
    is_valid: bool
    unique_identifier: Optional[str] = None
    owner: Optional[str] = None
    repository: Optional[str] = None
    package_name: Optional[str] = None
    version: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RepositoryData:
    platform: str
    identifier: str
    name: str
    description: Optional[str] = None
    stars: Optional[int] = None
    forks: Optional[int] = None
    watchers: Optional[int] = None
    issues_count: Optional[int] = None
    contributors_count: Optional[int] = None
    language: Optional[str] = None
    license: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    downloads_last_month: Optional[int] = None
    dependencies: Optional[List[str]] = None
    dev_dependencies: Optional[List[str]] = None
    version: Optional[str] = None
    homepage: Optional[str] = None
    repository_url: Optional[str] = None
    error_message: Optional[str] = None
    success: bool = True
    siblings: Optional[List[Any]] = None
    readme: Optional[str] = None
    
    # Additional HuggingFace-specific fields
    author: Optional[str] = None
    sha: Optional[str] = None
    last_modified: Optional[str] = None
    private: Optional[bool] = None
    gated: Optional[bool] = None
    disabled: Optional[bool] = None
    tags: Optional[List[str]] = None
    citation: Optional[str] = None
    paperswithcode_id: Optional[str] = None
    downloads: Optional[int] = None
    likes: Optional[int] = None
    card_data: Optional[str] = None
    used_storage: Optional[int] = None
    pipeline_tag: Optional[str] = None
    library_name: Optional[str] = None
    model_id: Optional[str] = None
    mask_token: Optional[str] = None
    widget_data: Optional[str] = None
    model_index: Optional[str] = None
    config: Optional[str] = None
    transformers_info: Optional[str] = None
    spaces: Optional[List[str]] = None
    safetensors: Optional[List[str]] = None
    inference: Optional[bool] = None
    dataset_present: Optional[bool] = None
    code_present: Optional[bool] = None