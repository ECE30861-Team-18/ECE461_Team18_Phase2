import json
import os
import difflib
import re
import boto3
import ast
import traceback  # <<< LOGGING
from string import Template
from typing import Any, Dict

from auth import require_auth
from metric_calculator import MetricCalculator
from url_handler import URLHandler
from url_category import URLCategory
from url_data import URLData
from data_retrieval import DataRetriever
from rds_connection import run_query

S3_BUCKET = os.environ.get("S3_BUCKET")
sqs_client = boto3.client("sqs")
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
DEPENDENCY_CAP_TYPES = ("dataset", "code")
DATASET_LINK_THRESHOLD = 0.75
CODE_LINK_THRESHOLD = 0.75


# -----------------------------
# DATASET/CODE DEPENDENCY EXTRACTION (SEPARATE FROM LINEAGE)
# -----------------------------
def extract_frontmatter_datasets(readme: str) -> list:
    """
    Extract dataset names from YAML frontmatter at top of README.
    Example:
    ---
    datasets:
    - bookcorpus
    - wikipedia
    ---
    """
    import re

    # Match YAML frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", readme, re.DOTALL)
    if not frontmatter_match:
        return []

    frontmatter = frontmatter_match.group(1)
    datasets = []

    # Look for datasets: section
    in_datasets = False
    for line in frontmatter.split("\n"):
        line = line.strip()

        if line.startswith("datasets:"):
            in_datasets = True
            continue

        if in_datasets:
            # Check if still in list (starts with -)
            if line.startswith("- "):
                dataset_name = line[2:].strip()
                if dataset_name:
                    datasets.append(dataset_name)
            elif line and not line.startswith("#"):
                # Hit next section
                in_datasets = False

    return datasets


def extract_github_urls(readme: str) -> list:
    """
    Extract all GitHub repository URLs from README.
    Handles markdown links like: [text](https://github.com/org/repo)
    And plain URLs: https://github.com/org/repo
    """
    import re

    github_urls = set()

    # Pattern 1: Markdown links [text](https://github.com/...)
    markdown_pattern = r"\[([^\]]+)\]\((https?://github\.com/[^\)]+)\)"
    for match in re.finditer(markdown_pattern, readme):
        github_urls.add(match.group(2))

    # Pattern 2: Plain URLs https://github.com/...
    url_pattern = r"https?://github\.com/[\w\-]+/[\w\-\.]+"
    for match in re.finditer(url_pattern, readme):
        url = match.group(0)
        # Clean up trailing punctuation
        url = url.rstrip(".),;:")
        github_urls.add(url)

    return list(github_urls)


def extract_artifact_dependencies(readme: str) -> dict:
    """
    Extract dataset and code repo mentions from model README.
    First tries YAML frontmatter and regex for GitHub URLs, then uses LLM for datasets.
    """
    if not readme or len(readme.strip()) < 50:
        return {"training_datasets": [], "eval_datasets": [], "code_repos": []}

    # Step 1: Extract from frontmatter (most reliable)
    frontmatter_datasets = extract_frontmatter_datasets(readme)

    # Step 2: Extract GitHub URLs directly (covers most cases like bert-base-uncased)
    github_urls = extract_github_urls(readme)

    # Step 3: Always use LLM to extract keywords (even if we have frontmatter)
    # Frontmatter gives exact names, LLM adds flexible matching keywords
    if frontmatter_datasets:
        print(
            f"[DEPENDENCY] Found datasets in frontmatter: {frontmatter_datasets}")
        print(f"[DEPENDENCY] Using LLM for code repos only")
    if github_urls:
        print(f"[DEPENDENCY] Found GitHub URLs: {github_urls}")
        print(f"[DEPENDENCY] Using LLM to add keywords for flexible matching")
    prompt_template = Template(
        """Analyze the following machine learning model README and extract dataset names and code repository references.

Your goal is to output ONLY structured JSON describing:
1. Datasets explicitly mentioned in the README
2. Code repositories explicitly mentioned in the README
3. Keywords that help identify these items (for downstream fuzzy matching)

============================================================
                EXTRACTION RULES (READ CAREFULLY)
============================================================

You MUST follow these rules strictly.

-------------------------------------
1. DATASET EXTRACTION RULES
-------------------------------------

Extract datasets ONLY when they explicitly appear in the README text.
Valid sources include:
• YAML frontmatter (if present)
• Any sentence that clearly refers to a dataset
• Tables, bullet lists, citations, or metadata fields that explicitly identify a dataset

Valid dataset signals include phrases such as:
“trained on X”, “fine-tuned on X”, “evaluated on X”, “uses the X dataset”, etc.

You MUST:
• Extract the dataset name EXACTLY as written in the README.
• Preserve original punctuation such as slashes or underscores.
• Not normalize or transform dataset names.
• Not infer or guess dataset identifiers.
• Not generate dataset names based on model names or author names.

You MUST generate dataset “keywords”:
• Lowercase tokens derived from the dataset name.
• Only include specific identifying tokens.
• Do NOT include generic words like “dataset”, “data”, “train”, “evaluate”, etc.

If the README does NOT distinguish training vs. eval datasets, place all extracted datasets into “training_datasets”.
If no datasets are present, output empty lists for both training_datasets and eval_datasets.

-------------------------------------
2. CODE REPOSITORY EXTRACTION RULES
-------------------------------------

Identify GitHub repositories ONLY if they explicitly appear in the README.

Valid signals:
• A literal GitHub URL
• A markdown hyperlink containing a GitHub URL
• A sentence referencing a GitHub repo with a visible URL

You MUST:
• Extract the FULL URL exactly as shown.
• Not modify the URL.
• Not infer or guess missing URLs.
• Not add URLs that do not appear in the README.

You MUST generate code repo “keywords”:
• Lowercase, non-generic identifying tokens derived from the URL (e.g., organization or repo name).
• Do NOT use generic words such as “code”, “repo”, “implementation”, “model”, “training”, etc.

If no repos are present, output “code_repos: []”.

-------------------------------------
3. STRICT NON-HALLUCINATION POLICY
-------------------------------------

You MUST NOT:
• Invent datasets or URLs not present in the README.
• Add datasets because the model name resembles a dataset.
• Add code repos unless a GitHub URL is explicitly shown.
• Infer normalized dataset names.
• Output descriptive text of any kind.
• Produce markdown formatting.
• Copy patterns from common examples or known datasets.

If the README contains NO datasets and NO GitHub URLs, all lists MUST be empty.

-------------------------------------
4. OUTPUT SCHEMA (MANDATORY)
-------------------------------------

Return ONLY this JSON structure:

{
  "training_datasets": [
    {"name": "...", "keywords": ["...", "..."]}
  ],
  "eval_datasets": [
    {"name": "...", "keywords": ["...", "..."]}
  ],
  "code_repos": [
    {"url": "https://github.com/.../...", "keywords": ["...", "..."]}
  ]
}

No other fields are allowed.

-------------------------------------
5. NO EXPLANATIONS OR MARKDOWN
-------------------------------------
Produce ONLY valid JSON. No comments, no text, no notes.

============================================================
README:
$readme_snippet
============================================================
"""
    )
    prompt = prompt_template.substitute(readme_snippet=readme[:4000])

    try:
        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"].strip()

        # Remove markdown code blocks
        if content.startswith("```"):
            content = content.split(
                "\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content.rsplit(
                "\n", 1)[0] if "\n" in content else content[:-3]

        try:
            extracted = json.loads(content)
        except Exception:
            print(
                "[DEPENDENCY] LLM returned invalid JSON, falling back to empty dependencies"
            )
            extracted = {"training_datasets": [],
                         "eval_datasets": [], "code_repos": []}

        print(f"[DEPENDENCY] LLM extracted: {extracted}")

        # Normalize LLM output to include keywords
        normalized: dict = {
            "training_datasets": [],
            "eval_datasets": [],
            "code_repos": [],
        }

        # Merge frontmatter datasets (exact names) with LLM keywords
        if frontmatter_datasets:
            # Build a map of LLM dataset names to their keywords
            llm_dataset_keywords = {}
            for ds in extracted.get("training_datasets", []) + extracted.get(
                "eval_datasets", []
            ):
                if isinstance(ds, dict):
                    ds_name = ds.get("name", "").lower()
                    ds_keywords = ds.get("keywords", [])
                    if ds_name:
                        llm_dataset_keywords[ds_name] = ds_keywords

            # Use frontmatter names but add LLM keywords if found
            for fm_ds in frontmatter_datasets:
                fm_ds_lower = fm_ds.lower()
                keywords = llm_dataset_keywords.get(fm_ds_lower, [])

                # If no exact match, try to find partial match
                if not keywords:
                    for llm_name, llm_kw in llm_dataset_keywords.items():
                        if fm_ds_lower in llm_name or llm_name in fm_ds_lower:
                            keywords = llm_kw
                            break

                # Add default keyword if LLM didn't provide any
                if not keywords:
                    keywords = [fm_ds_lower]

                normalized["training_datasets"].append(
                    {"name": fm_ds, "keywords": keywords}
                )

            print(
                f"[DEPENDENCY] Merged frontmatter datasets with LLM keywords: {normalized['training_datasets']}"
            )
        else:
            # Use LLM datasets with keywords
            for ds in extracted.get("training_datasets", []):
                if isinstance(ds, dict):
                    normalized["training_datasets"].append(ds)
                else:
                    normalized["training_datasets"].append(
                        {"name": ds, "keywords": [ds.lower()]}
                    )

            for ds in extracted.get("eval_datasets", []):
                if isinstance(ds, dict):
                    normalized["eval_datasets"].append(ds)
                else:
                    normalized["eval_datasets"].append(
                        {"name": ds, "keywords": [ds.lower()]}
                    )

        # Always use LLM for code repos (with keywords for flexibility)
        # Merge regex-extracted URLs with LLM-extracted repos and keywords
        all_code_repos = []
        url_to_keywords = {}

        # First, collect LLM-extracted repos with their keywords
        for repo in extracted.get("code_repos", []):
            if isinstance(repo, dict):
                repo_url = repo.get("url", "")
                repo_keywords = repo.get("keywords", [])
                if repo_url:
                    url_to_keywords[repo_url.lower()] = repo_keywords
                    all_code_repos.append(
                        {"url": repo_url, "keywords": repo_keywords})
            else:
                # Old format - just URL string
                if repo:
                    url_to_keywords[repo.lower()] = []
                    all_code_repos.append({"url": repo, "keywords": []})

        # Add regex-extracted URLs that weren't already found by LLM
        if github_urls:
            for url in github_urls:
                # Check if this URL was already added by LLM
                url_lower = url.lower()
                already_added = False
                for existing_url in url_to_keywords.keys():
                    # Normalize both URLs for comparison (remove .git, trailing slashes)
                    norm_url = url_lower.rstrip("/").rstrip(".git")
                    norm_existing = existing_url.rstrip("/").rstrip(".git")
                    if norm_url == norm_existing:
                        already_added = True
                        break

                if not already_added:
                    # Add with empty keywords since LLM didn't extract it
                    all_code_repos.append({"url": url, "keywords": []})

        normalized["code_repos"] = all_code_repos

        return normalized

    except Exception as e:
        print(f"[DEPENDENCY] Failed to extract: {e}")
        return {"training_datasets": [], "eval_datasets": [], "code_repos": []}


def extract_dependencies_from_code_readme(readme: str) -> dict:
    """
    Extract dataset names from code repository README.
    Code repos are ingested last and can reference datasets.
    """
    if not readme or len(readme.strip()) < 50:
        return {"datasets": []}

    prompt_template = Template(
        """Analyze the following code repository README and extract ONLY the datasets explicitly mentioned.

============================================================
                EXTRACTION RULES (READ CAREFULLY)
============================================================

You MUST follow these rules:

-------------------------------------
1. DATASET EXTRACTION
-------------------------------------

Extract dataset names ONLY when they explicitly appear in the README text.

Valid signals include phrases such as:
• "trained on X"
• "we use X"
• "evaluated on X"
• "tested on X dataset"
• "supports X"
• Any direct text reference to a dataset name

You MUST:
• Extract the dataset name EXACTLY as it appears in the README.
• Preserve punctuation such as slashes or underscores.
• Not normalize or transform the dataset name.
• Not infer or guess dataset identifiers.

-------------------------------------
2. MULTIPLE DATASETS
-------------------------------------

If multiple datasets are mentioned explicitly, include all of them.

-------------------------------------
3. STRICT NON-HALLUCINATION POLICY
-------------------------------------

You MUST NOT:
• Add datasets that do not appear in the README.
• Infer datasets based on context, model names, repo names, or common ML knowledge.
• Generate dataset names from patterns or assumptions.
• Return any dataset not literally present in the text.

If the README does not mention any dataset, return an empty list.

-------------------------------------
4. OUTPUT SCHEMA (MANDATORY)
-------------------------------------

Return ONLY this JSON structure:

{
  "datasets": ["dataset1", "dataset2"]
}

Where:
• Each dataset is a lowercase string.
• If no datasets are present, return `"datasets": []`.

-------------------------------------
5. NO EXPLANATIONS, NO MARKDOWN
-------------------------------------

Only return valid JSON. No comments, no natural language, no markdown.

============================================================
README:
$readme_snippet
============================================================
"""
    )
    prompt = prompt_template.substitute(readme_snippet=readme[:4000])

    try:
        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 800,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"].strip()

        if content.startswith("```"):
            content = content.split(
                "\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content.rsplit(
                "\n", 1)[0] if "\n" in content else content[:-3]

        try:
            extracted = json.loads(content)
        except Exception:
            print(
                "[DEPENDENCY] LLM returned invalid JSON, falling back to empty dependencies"
            )
            extracted = {"training_datasets": [],
                         "eval_datasets": [], "code_repos": []}

        print(f"[DEPENDENCY] Code repo datasets: {extracted}")
        return extracted

    except Exception as e:
        print(f"[DEPENDENCY] Failed to extract from code: {e}")
        return {"datasets": []}


def matches_identifier(artifact_name: str, source_url: str, expected: str) -> bool:
    """
    Check if an artifact matches an expected identifier.
    Uses strict matching to avoid false positives with generic terms.
    """
    if not expected or len(expected) < 3:
        return False

    expected_lower = expected.lower().strip()
    artifact_name_lower = artifact_name.lower().strip()

    # Special handling for GitHub URLs - must match closely
    if (
        "github.com" in expected_lower
        and source_url
        and "github.com" in source_url.lower()
    ):
        import re

        def extract_repo_path(url):
            match = re.search(r"github\.com/([\w\-]+/[\w\-\.]+)", url.lower())
            if match:
                return match.group(1).rstrip(".git")
            return None

        expected_path = extract_repo_path(expected_lower)
        source_path = extract_repo_path(source_url.lower())

        if expected_path and source_path:
            # Exact match
            if expected_path == source_path:
                return True

            # Check org/repo components
            expected_parts = expected_path.split("/")
            source_parts = source_path.split("/")

            if len(expected_parts) == 2 and len(source_parts) == 2:
                expected_org, expected_repo = expected_parts
                source_org, source_repo = source_parts

                # Both org AND repo must have substantial overlap
                org_match = expected_org in source_org or source_org in expected_org
                repo_match = (
                    expected_repo in source_repo or source_repo in expected_repo
                )

                # Require BOTH to match
                if org_match and repo_match:
                    return True

    # For non-URL matching, require much stricter criteria
    expected_normalized = (
        expected_lower.replace("-", "").replace("_", "").replace(" ", "")
    )
    artifact_normalized = (
        artifact_name_lower.replace("-", "").replace("_", "").replace(" ", "")
    )

    # Exact match
    if expected_normalized == artifact_normalized:
        return True

    # For dataset names: check if expected is substantial part (> 50% of artifact name)
    if len(expected_normalized) >= 5:
        # Check if expected is a significant part
        if expected_normalized in artifact_normalized:
            # Must be at least 50% of the artifact name to match
            overlap_ratio = len(expected_normalized) / len(artifact_normalized)
            if overlap_ratio >= 0.5:
                return True

        # Check reverse
        if artifact_normalized in expected_normalized:
            overlap_ratio = len(artifact_normalized) / len(expected_normalized)
            if overlap_ratio >= 0.5:
                return True

    # Check suffix matching for datasets (e.g., "rajpurkar-squad" ends with "squad")
    if artifact_name_lower.endswith(
        "-" + expected_lower
    ) or artifact_name_lower.endswith("_" + expected_lower):
        return True

    return False


def normalize_identifier(text: str) -> str:
    """Normalize identifiers for comparison."""
    if not text:
        return ""
    cleaned = text.lower().strip()
    cleaned = cleaned.strip(".,;:/\\()[]{}\"'")
    cleaned = re.sub(r"[_-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def token_overlap_score(a: str, b: str) -> float:
    """Compute Jaccard similarity on tokens."""
    norm_a = normalize_identifier(a)
    norm_b = normalize_identifier(b)
    if not norm_a or not norm_b:
        return 0.0
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def fuzzy_string_similarity(a: str, b: str) -> float:
    """Fuzzy similarity using SequenceMatcher."""
    norm_a = normalize_identifier(a)
    norm_b = normalize_identifier(b)
    if not norm_a or not norm_b:
        return 0.0
    return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()


def compute_identifier_score(
    artifact_name: str, source_url: str, expected: str
) -> float:
    """Combine strict match with fuzzy/token similarity into a score."""
    if not expected:
        return 0.0

    # Strong signal if strict matcher succeeds
    if matches_identifier(artifact_name, source_url, expected):
        return 1.0

    norm_artifact = normalize_identifier(artifact_name)
    norm_expected = normalize_identifier(expected)
    if not norm_artifact or not norm_expected:
        return 0.0

    score = 0.0
    token_score = token_overlap_score(norm_artifact, norm_expected)
    score = max(score, token_score)
    score = max(score, fuzzy_string_similarity(norm_artifact, norm_expected))

    # Token subset boost: if all expected tokens appear in the artifact (or vice versa)
    expected_tokens = set(norm_expected.split())
    artifact_tokens = set(norm_artifact.split())
    if expected_tokens and artifact_tokens:
        if expected_tokens.issubset(artifact_tokens):
            score = max(score, min(1.0, 0.85 + 0.05 *
                        min(len(expected_tokens), 2)))
        if artifact_tokens.issubset(expected_tokens):
            score = max(score, min(1.0, 0.85 + 0.05 *
                        min(len(artifact_tokens), 2)))

    # Small boosts for substring containment
    if norm_expected in norm_artifact and len(norm_expected) >= 3:
        score = max(score, 0.8 * (len(norm_expected) /
                    max(len(norm_artifact), 1)))
    if norm_artifact in norm_expected and len(norm_artifact) >= 3:
        score = max(score, 0.8 * (len(norm_artifact) /
                    max(len(norm_expected), 1)))

    return max(0.0, min(1.0, score))


def compute_dataset_link_score(
    metadata: dict, artifact_name: str, source_url: str
) -> float:
    """Score how well a dataset matches a model's expected datasets."""
    raw = metadata.get("expected_dependencies", {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except:
            raw = {}
    deps = raw if isinstance(raw, dict) else {}
    candidates = deps.get("training_datasets", []) + \
        deps.get("eval_datasets", [])

    max_score = 0.0
    for entry in candidates:
        name = ""
        keywords: list[str] = []
        if isinstance(entry, dict):
            name = entry.get("name", "") or ""
            keywords = entry.get("keywords", []) or []
        else:
            name = entry

        for candidate in [name] + list(keywords):
            if not candidate:
                continue
            score = compute_identifier_score(
                artifact_name, source_url, candidate)
            if score > max_score:
                max_score = score

    return max_score


def compute_code_link_score(
    metadata: dict, artifact_name: str, source_url: str, code_datasets: list
) -> float:
    """Score how well a code repo matches a model's expected code repos or datasets."""
    raw = metadata.get("expected_dependencies", {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except:
            raw = {}
    deps = raw if isinstance(raw, dict) else {}
    code_repos = deps.get("code_repos", [])

    max_code_repo_score = 0.0
    for entry in code_repos:
        expected_url = ""
        keywords: list[str] = []
        if isinstance(entry, dict):
            expected_url = entry.get("url", "") or ""
            keywords = entry.get("keywords", []) or []
        else:
            expected_url = entry

        for candidate in [expected_url] + list(keywords):
            if not candidate:
                continue
            score = compute_identifier_score(
                artifact_name, source_url, candidate)
            if score > max_code_repo_score:
                max_code_repo_score = score

    # Architecture-aware matching (e.g., resnet-50 ↔ KaimingHe repo)
    model_name = (metadata.get("name") or "").lower()
    artifact_norm = normalize_identifier(artifact_name)

    # Detect architecture tokens such as resnet-50
    arch_terms = []
    match = re.findall(r"(resnet[-_]?\d+)", model_name)
    if match:
        arch_terms.extend(match)
    if "resnet" in model_name:
        arch_terms.append("resnet")

    for token in arch_terms:
        if token in artifact_norm:
            max_code_repo_score = max(max_code_repo_score, 0.90)

    return max_code_repo_score


def _normalize_repo_url(url: str) -> str:
    """Normalize repo URLs for comparison."""
    if not url:
        return ""
    normalized = url.strip().lower()
    normalized = normalized.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized


def find_and_link_to_models(
    artifact_id: int,
    artifact_type: str,
    artifact_name: str,
    source_url: str,
    artifact_metadata: dict,
):
    """
    Layer 1 linking only:
    - dataset: dash-split keywords matched against model metadata tags that start with "dataset:".
    - code: repository_url matched against model expected_dependencies.code_repos URLs.
    """
    print(f"[DEPENDENCY] Layer1 linking {artifact_type} '{artifact_name}' to models...")

    models = run_query(
        "SELECT id, name, metadata FROM artifacts WHERE type = 'model';", fetch=True
    )

    if not models:
        print("[DEPENDENCY] No models found")
        return

    links_created = 0
    linked_model_ids = []

    dataset_keywords = []
    if artifact_type == "dataset":
        dataset_keywords = [
            part.strip().lower()
            for part in artifact_name.split("-")
            if part and part.strip()
        ]

    artifact_repo_url = _normalize_repo_url(source_url)

    for model in models:
        model_id = model.get("id")
        metadata = model.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                continue

        if artifact_type == "dataset":
            tags = metadata.get("tags", []) or []
            matched = False
            for tag in tags:
                if not isinstance(tag, str):
                    continue
                tag_lower = tag.lower().strip()
                if not tag_lower.startswith("dataset:"):
                    continue
                tag_value = tag_lower.split(":", 1)[1].strip()
                if not tag_value:
                    continue
                if any(kw == tag_value or kw in tag_value or tag_value in kw for kw in dataset_keywords):
                    matched = True
                    break

            if matched:
                try:
                    run_query(
                        """
                        INSERT INTO artifact_dependencies 
                        (model_id, artifact_id, model_name, dependency_name, dependency_type, source)
                        VALUES (%s, %s, %s, %s, %s, 'layer1_tags')
                        ON CONFLICT DO NOTHING;
                        """,
                        (
                            model_id,
                            artifact_id,
                            model.get("name"),
                            artifact_name,
                            "dataset",
                        ),
                        fetch=False,
                    )
                    links_created += 1
                    linked_model_ids.append(model_id)
                    print(
                        f"[DEPENDENCY] Layer1 linked dataset {artifact_name} -> model {model_id} via tag match"
                    )
                except Exception as e:
                    print(f"[DEPENDENCY] Failed to link dataset via layer1: {e}")

        elif artifact_type == "code":
            if not artifact_repo_url:
                continue

            raw_deps = metadata.get("expected_dependencies", {})
            if isinstance(raw_deps, str):
                try:
                    raw_deps = json.loads(raw_deps)
                except Exception:
                    raw_deps = {}

            code_repos: list = []
            if isinstance(raw_deps, dict):
                code_repos = raw_deps.get("code_repos", []) or []

            matched = False
            for entry in code_repos:
                if isinstance(entry, dict):
                    candidate_url = entry.get("url", "")
                else:
                    candidate_url = entry
                norm_candidate = _normalize_repo_url(candidate_url)
                if norm_candidate and norm_candidate == artifact_repo_url:
                    matched = True
                    break

            if matched:
                try:
                    run_query(
                        """
                        INSERT INTO artifact_dependencies 
                        (model_id, artifact_id, model_name, dependency_name, dependency_type, source)
                        VALUES (%s, %s, %s, %s, %s, 'layer1_code_repo')
                        ON CONFLICT DO NOTHING;
                        """,
                        (
                            model_id,
                            artifact_id,
                            model.get("name"),
                            artifact_name,
                            "code",
                        ),
                        fetch=False,
                    )
                    links_created += 1
                    linked_model_ids.append(model_id)
                    print(
                        f"[DEPENDENCY] Layer1 linked code repo {artifact_name} -> model {model_id} via code_repo match"
                    )
                except Exception as e:
                    print(f"[DEPENDENCY] Failed to link code via layer1: {e}")

    print(f"[DEPENDENCY] Layer1 created {links_created} links for '{artifact_name}'")

    if linked_model_ids:
        recalculate_model_ratings(linked_model_ids)


def recalculate_model_ratings(model_ids: list):
    """
    Update only dataset_quality and code_quality metrics after linking dependencies.
    Preserves other expensive metrics (performance, reproducibility) from original rating.
    """
    from submetrics import DatasetQualityMetric, CodeQualityMetric

    for model_id in model_ids:
        try:
            model_result = run_query(
                "SELECT id, metadata, ratings FROM artifacts WHERE id = %s;",
                (model_id,),
                fetch=True,
            )

            if not model_result:
                continue

            model = model_result[0]

            # Parse metadata and ratings (handle both dict and JSON string)
            metadata = model.get("metadata", {})
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            ratings = model.get("ratings", {})
            if isinstance(ratings, str):
                ratings = json.loads(ratings)

            # Add model ID for queries
            metadata["id"] = model_id

            # Recalculate only dependency-related metrics
            dataset_metric = DatasetQualityMetric()
            code_metric = CodeQualityMetric()

            ratings["dataset_quality"] = dataset_metric.calculate_metric(
                metadata)
            ratings["code_quality"] = code_metric.calculate_metric(metadata)

            # Recalculate net_score with updated metrics (all weights are 0.125)
            net_score = 0.0
            for key, value in ratings.items():
                if key.endswith("_latency") or key in [
                    "net_score",
                    "net_score_latency",
                    "category",
                ]:
                    continue
                if isinstance(value, dict):
                    net_score += (
                        sum(value.values()) / len(value) if value else 0.0
                    ) * 0.125
                else:
                    net_score += float(value) * 0.125

            ratings["net_score"] = round(net_score, 3)

            # Update database
            run_query(
                "UPDATE artifacts SET ratings = %s, net_score = %s WHERE id = %s;",
                (json.dumps(ratings), ratings["net_score"], model_id),
                fetch=False,
            )

        except Exception as e:
            print(f"[RATING UPDATE] Failed for model {model_id}: {e}")


# -----------------------------
# LOGGING HELPERS
# -----------------------------
def log_event(event, context):  # <<< LOGGING
    print("==== INCOMING EVENT ====")
    try:
        print(json.dumps(event, indent=2))
    except:
        print(event)

    print("==== CONTEXT ====")
    try:
        print(
            json.dumps(
                {
                    "aws_request_id": context.aws_request_id,
                    "function_name": context.function_name,
                    "memory_limit_in_mb": context.memory_limit_in_mb,
                    "function_version": context.function_version,
                },
                indent=2,
            )
        )
    except:
        pass


def log_response(response):  # <<< LOGGING
    print("==== OUTGOING RESPONSE ====")
    try:
        print(json.dumps(response, indent=2))
    except:
        print(response)


def log_exception(e):  # <<< LOGGING
    print("==== EXCEPTION OCCURRED ====")
    print(str(e))
    traceback.print_exc()


# -----------------------------
# Lambda Handler
# -----------------------------
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:

    log_event(event, context)  # <<< LOGGING

    # Validate authentication
    valid, error_response = require_auth(event)
    if not valid:
        return error_response

    try:
        body = json.loads(event.get("body", "{}"))
        url = body.get("url")
        provided_name = body.get("name")

        # NEW: Accept optional relationship info
        related_model_id = body.get(
            "related_model_id"
        )  # For datasets/code that belong to a model
        relationship_type = body.get(
            "relationship_type"
        )  # e.g., "dataset", "code", "fine_tuning_dataset"

        artifact_type = event.get("pathParameters", {}).get("artifact_type")

        # --------------------------
        # 2. Validate request
        # --------------------------
        if not url or not artifact_type:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing URL or artifact_type"}),
            }
            log_response(response)  # <<< LOGGING
            return response

        # Use URLHandler to extract identifier
        url_handler_temp = URLHandler()
        parsed_data = url_handler_temp.handle_url(url)
        identifier = parsed_data.unique_identifier

        # >>> MINIMAL CHANGE: type-aware URL validation <<<
        if not identifier:
            response = {"statusCode": 400,
                        "body": json.dumps({"error": "Invalid URL"})}
            log_response(response)  # <<< LOGGING
            return response

        # Allow clients to override the derived identifier with a friendly name
        if provided_name is not None:
            if not isinstance(provided_name, str) or not provided_name.strip():
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid name"}),
                }
                log_response(response)  # <<< LOGGING
                return response
            artifact_name = provided_name.strip()
        else:
            artifact_name = identifier

        if artifact_type == "model":
            if parsed_data.category != URLCategory.HUGGINGFACE:
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Model must use a Hugging Face URL"}),
                }
                log_response(response)  # <<< LOGGING
                return response
        elif artifact_type == "dataset":
            if parsed_data.category not in (
                URLCategory.HUGGINGFACE,
                URLCategory.GITHUB,
                URLCategory.KAGGLE,
            ):
                response = {
                    "statusCode": 400,
                    "body": json.dumps(
                        {
                            "error": "Dataset must use a Hugging Face, GitHub, or Kaggle URL"
                        }
                    ),
                }
                log_response(response)  # <<< LOGGING
                return response
        elif artifact_type == "code":
            if parsed_data.category != URLCategory.GITHUB:
                response = {
                    "statusCode": 400,
                    "body": json.dumps(
                        {"error": "Code artifacts must use a GitHub URL"}
                    ),
                }
                log_response(response)  # <<< LOGGING
                return response
        else:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid artifact_type"}),
            }
            log_response(response)  # <<< LOGGING
            return response

        # --------------------------
        # 3. Duplicate check (using source_url)
        # --------------------------
        check_result = run_query(
            "SELECT id FROM artifacts WHERE source_url = %s AND type = %s;",
            (url, artifact_type),
            fetch=True,
        )

        if check_result:
            response = {
                "statusCode": 409,
                "body": json.dumps(
                    {"error": "Artifact already exists",
                        "id": check_result[0]["id"]}
                ),
            }
            log_response(response)  # <<< LOGGING
            return response

        # --------------------------
        # 4. RATING PIPELINE (only for models)
        # --------------------------
        url_handler = URLHandler()
        data_retriever = DataRetriever(
            github_token=os.environ.get("GITHUB_TOKEN"),
            hf_token=os.environ.get("HF_TOKEN"),
        )

        model_obj: URLData = url_handler.handle_url(url)

        if not model_obj.is_valid:
            response = {
                "statusCode": 400,
                "body": json.dumps({"error": "URL is not valid"}),
            }
            log_response(response)  # <<< LOGGING
            return response

        if artifact_type == "model":
            if model_obj.category != URLCategory.HUGGINGFACE:
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Model must use a Hugging Face URL"}),
                }
                log_response(response)  # <<< LOGGING
                return response
        elif artifact_type == "dataset":
            if model_obj.category not in (
                URLCategory.HUGGINGFACE,
                URLCategory.GITHUB,
                URLCategory.KAGGLE,
            ):
                response = {
                    "statusCode": 400,
                    "body": json.dumps(
                        {
                            "error": "Dataset must use a Hugging Face, GitHub, or Kaggle URL"
                        }
                    ),
                }
                log_response(response)  # <<< LOGGING
                return response
        elif artifact_type == "code":
            if model_obj.category != URLCategory.GITHUB:
                response = {
                    "statusCode": 400,
                    "body": json.dumps({"error": "URL is not a valid GitHub URL"}),
                }
                log_response(response)  # <<< LOGGING
                return response

        repo_data = data_retriever.retrieve_data(model_obj)

        model_dict = {**repo_data.__dict__, "name": artifact_name}

        # Only calculate metrics for models
        if artifact_type == "model":
            calc = MetricCalculator()
            rating = calc.calculate_all_metrics(model_dict, category="MODEL")
            net_score = rating["net_score"]
        else:
            rating = {}
            net_score = None

        metadata_dict = repo_data.__dict__.copy()
        metadata_dict["requested_name"] = artifact_name
        if metadata_dict.get("created_at"):
            metadata_dict["created_at"] = metadata_dict["created_at"].isoformat()
        if metadata_dict.get("updated_at"):
            metadata_dict["updated_at"] = metadata_dict["updated_at"].isoformat()

        # Extract dataset/code dependencies for models (separate from lineage)
        if artifact_type == "model":
            readme_text = metadata_dict.get("readme", "")
            if readme_text:
                print(f"[DEPENDENCY] Extracting dependencies from model README...")
                dependencies = extract_artifact_dependencies(readme_text)
                if dependencies and any(dependencies.values()):
                    metadata_dict["expected_dependencies"] = dependencies
                    print(f"[DEPENDENCY] Stored: {dependencies}")

        metadata_json = json.dumps(metadata_dict)

        # --------------------------
        # 6. Insert as upload_pending with download_url
        # --------------------------
        # First get the artifact_id, then construct download_url
        result = run_query(
            """
            INSERT INTO artifacts (type, name, source_url, net_score, ratings, status, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                artifact_type,
                artifact_name,
                url,
                net_score,
                json.dumps(rating),
                "upload_pending",
                metadata_json,
            ),
            fetch=True,
        )

        artifact_id = result[0]["id"]

        # Generate proper S3 HTTPS URL immediately
        download_url = f"https://{S3_BUCKET}.s3.us-east-1.amazonaws.com/{artifact_type}/{artifact_id}/"

        # Update the artifact with download_url
        run_query(
            """
            UPDATE artifacts
            SET download_url = %s
            WHERE id = %s;
            """,
            (download_url, artifact_id),
            fetch=False,
        )
        
        # Recalculate metrics with artifact_id for TreeScore calculation
        if artifact_type == "model":
            model_dict["artifact_id"] = artifact_id
            calc_with_id = MetricCalculator()
            rating_with_treescore = calc_with_id.calculate_all_metrics(model_dict, category="MODEL")
            
            # Update ratings with TreeScore included
            run_query(
                """
                UPDATE artifacts
                SET ratings = %s, net_score = %s
                WHERE id = %s;
                """,
                (json.dumps(rating_with_treescore), rating_with_treescore["net_score"], artifact_id),
                fetch=False,
            )

        # --------------------------
        # 6a. Link dataset/code to models (uses artifact_dependencies table)
        # --------------------------
        if artifact_type in ("dataset", "code"):
            find_and_link_to_models(
                artifact_id, artifact_type, artifact_name, url, metadata_dict
            )

        # --------------------------
        # 6b. Auto-extract MODEL lineage from config.json (uses artifact_relationships table)
        # --------------------------

        auto_relationships = []

        # Load config.json (stringified JSON)
        raw_config = metadata_dict.get("config")
        try:
            print("[AUTOGRADER DEBUG LINEAGE] Raw config JSON for artifact",
                  artifact_name, raw_config)

            if isinstance(raw_config, dict):
                config = raw_config
            elif isinstance(raw_config, str):
                config = ast.literal_eval(raw_config) if raw_config else {}

            print("[AUTOGRADER DEBUG LINEAGE] Parsed config JSON for artifact", config)
        except Exception as e:
            config = {}
            print("[AUTOGRADER DEBUG LINEAGE] Failed to parse config JSON for artifact", e)

        # Helper: insert relationship into DB (if parent exists)
        def add_auto_rel(parent_name, relationship_type):
            if not parent_name or not isinstance(parent_name, str):
                return

            candidates = [parent_name]

            # If HF-style org/name, also try short name
            if "/" in parent_name:
                candidates.append(parent_name.split("/")[-1])

            parent_query = None
            for candidate in candidates:
                parent_query = run_query(
                    "SELECT id FROM artifacts WHERE name = %s;",
                    (candidate,),
                    fetch=True,
                )
                if parent_query:
                    break

            if parent_query:
                parent_id = parent_query[0]["id"]

                run_query(
                    """
                    INSERT INTO artifact_relationships
                    (from_artifact_id, to_artifact_id, relationship_type, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (parent_id, artifact_id, relationship_type, "config_json"),
                    fetch=False,
                )

                auto_relationships.append(
                    {
                        "artifact_id": parent_id,
                        "relationship": relationship_type,
                        "direction": "from",
                    }
                )
                
            else:
                auto_relationships.append(
                    {
                        "artifact_id": parent_name,
                        "relationship": relationship_type,
                        "direction": "from",
                        "placeholder": True,
                    }
                )

        # ---- RULE 1: PEFT / LoRA / Adapter ----
        if "base_model_name_or_path" in config:
            print("[AUTOGRADER DEBUG LINEAGE] Found base_model_name_or_path:",
                  config["base_model_name_or_path"])
            add_auto_rel(config["base_model_name_or_path"], "base_model")

        # ---- RULE 2: Fine-tuned / derived checkpoint ----
        # Note: Avoid self-referential loops
        if "_name_or_path" in config:
            print("[AUTOGRADER DEBUG LINEAGE] Found _name_or_path:",
                  config["_name_or_path"])
            val = config["_name_or_path"]
            if isinstance(val, str) and val != artifact_name:
                add_auto_rel(val, "derived_from")

        # ---- RULE 3: finetuned_from ----
        if "finetuned_from" in config:
            print("[AUTOGRADER DEBUG LINEAGE] Found finetuned_from:",
                  config["finetuned_from"])
            add_auto_rel(config["finetuned_from"], "fine_tuned_from")

        # ---- RULE 4: Distillation teacher ----
        if "teacher" in config:
            print("[AUTOGRADER DEBUG LINEAGE] Found teacher:", config["teacher"])
            add_auto_rel(config["teacher"], "teacher_model")

        # ---- RULE 5: PEFT type (LoRA, prefix-tuning, etc.) ----
        if "peft_type" in config:
            print("[AUTOGRADER DEBUG LINEAGE] Found peft_type:",
                  config["peft_type"])
            base = config.get("base_model_name_or_path")
            peft_type = config["peft_type"].lower()
            if base:
                add_auto_rel(base, peft_type)

        # ---- RULE 6: model-index base model ----
        model_index_raw = metadata_dict.get("model_index")
        if model_index_raw:
            print("[AUTOGRADER DEBUG LINEAGE] Found model_index:", model_index_raw)
            try:
                model_index = json.loads(model_index_raw)
                if isinstance(model_index, list):
                    for entry in model_index:
                        training = entry.get("training", {})
                        base_model = training.get("base_model")
                if base_model:
                    print(
                        "[AUTOGRADER DEBUG LINEAGE] found model-index base_model:", base_model)
                    add_auto_rel(base_model, "base_model")
            except Exception as e:
                print("[AUTOGRADER DEBUG LINEAGE] Failed to parse model-index:", e)

        # Save auto lineage entries into metadata
        if auto_relationships:
            metadata_dict["auto_lineage"] = auto_relationships

        # --------------------------
        # 6c. Create lineage relationship if provided
        # --------------------------
        if related_model_id and relationship_type:
            print("[LINEAGE] Creating user-provided relationship:",
                  related_model_id, relationship_type)
            check_model = run_query(
                "SELECT id, type FROM artifacts WHERE id = %s;",
                (related_model_id,),
                fetch=True,
            )

            if check_model:
                # if artifact_type in ("dataset", "code"):
                if artifact_type == "model":
                    from_id = related_model_id
                    to_id = artifact_id
                    run_query(
                        """
                    INSERT INTO artifact_relationships (from_artifact_id, to_artifact_id, relationship_type, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (from_artifact_id, to_artifact_id, relationship_type) DO NOTHING;
                    """,
                        (from_id, to_id, relationship_type, "user_provided"),
                        fetch=False,
                    )

                metadata_dict["related_artifacts"] = metadata_dict.get(
                    "related_artifacts", []
                )
                metadata_dict["related_artifacts"].append(
                    {
                        "artifact_id": related_model_id,
                        "relationship": relationship_type,
                        "direction": (
                            "to" if artifact_type in (
                                "dataset", "code") else "from"
                        ),
                    }
                )

        if auto_relationships or related_model_id:
            run_query(
                """
                UPDATE artifacts
                SET metadata = %s
                WHERE id = %s;
                """,
                (json.dumps(metadata_dict), artifact_id), fetch=False
            )

        # --------------------------
        # 7. Send SQS message to ECS ingest worker
        # --------------------------
        sqs_client.send_message(
            QueueUrl=os.environ.get("INGEST_QUEUE_URL"),
            MessageBody=json.dumps(
                {
                    "artifact_id": artifact_id,
                    "artifact_type": artifact_type,
                    "identifier": identifier,
                    "source_url": url,
                }
            ),
        )

        # --------------------------
        # 8. SUCCESS (201)
        # --------------------------
        response = {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "metadata": {
                        "name": artifact_name,
                        "id": artifact_id,
                        "type": artifact_type,
                    },
                    "data": {"url": url, "download_url": download_url},
                }
            ),
        }

        log_response(response)  # <<< LOGGING
        return response

    except Exception as e:
        log_exception(e)  # <<< LOGGING
        response = {"statusCode": 500, "body": json.dumps({"error": str(e)})}
        log_response(response)  # <<< LOGGING
        return response
