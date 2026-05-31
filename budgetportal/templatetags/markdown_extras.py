from django import template
import re

register = template.Library()


@register.filter
def ensure_heading_blocks(text):
    """
    Normalize imported Markdown text before it reaches the markdown renderer.
    Handles literal '\n' values and trims inconsistent indentation without
    converting the content to HTML.
    """
    if not text:
        return ""

    text = text.replace("\\n", "\n")
    text = "\n".join(line.lstrip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()
