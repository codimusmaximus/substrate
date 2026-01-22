"""Obsidian vault sync logic."""
import hashlib
from pathlib import Path
from typing import Iterator
import yaml

from substrate.core.config import VAULT_PATH


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        frontmatter = {}

    body = parts[2].strip()
    return frontmatter, body


def extract_tags(content: str, frontmatter: dict) -> list[str]:
    """Extract tags from content and frontmatter."""
    tags = set()

    # From frontmatter
    if "tags" in frontmatter:
        fm_tags = frontmatter["tags"]
        if isinstance(fm_tags, list):
            for t in fm_tags:
                if t is not None:
                    t = str(t)
                    tags.add(f"#{t}" if not t.startswith("#") else t)
        elif fm_tags is not None:
            t = str(fm_tags)
            tags.add(f"#{t}" if not t.startswith("#") else t)

    # From content (inline tags)
    import re
    inline_tags = re.findall(r"#[\w/-]+", content)
    tags.update(inline_tags)

    return sorted(tags)


def iter_vault_files(vault_path: str = None) -> Iterator[dict]:
    """Iterate over all markdown files in vault."""
    vault = Path(vault_path or VAULT_PATH)

    for md_file in vault.rglob("*.md"):
        content = md_file.read_text()
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        frontmatter, body = parse_frontmatter(content)
        tags = extract_tags(content, frontmatter)

        yield {
            "file_path": str(md_file.relative_to(vault)),
            "file_hash": file_hash,
            "frontmatter": frontmatter,
            "title": frontmatter.get("title") or md_file.stem,
            "tags": tags,
            "content": body,
        }
