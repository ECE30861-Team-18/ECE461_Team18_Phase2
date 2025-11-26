"""
Enum containing the different URL categories
"""

from enum import Enum

class URLCategory(Enum):
    GITHUB = "github"
    NPM = "npm"
    HUGGINGFACE = "huggingface"
    KAGGLE = "kaggle"
    UNKNOWN = "unknown"