"""Notes domain business logic."""


def extract_links(content: str) -> list[str]:
    """Extract wikilinks from content."""
    import re
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def note_status(frontmatter: dict) -> str:
    """Get note status with fallback."""
    return frontmatter.get("status", "inbox")
