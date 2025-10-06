# myapp/templatetags/markdown_extras.py
from django import template
from markdown_it import MarkdownIt
import re
register = template.Library()

@register.filter
def ensure_heading_blocks(text):
    """
    Convert Markdown text to HTML using markdown-it-py.
    Handles literal '\n', headings, lists, paragraphs, and line breaks.
    """
    if not text:
        return ""

    # Step 1: Convert literal "\n" to real newlines
    text = text.replace("\\n", "\n")

    # Step 2: Strip leading/trailing whitespace from each line
    text = "\n".join(line.lstrip() for line in text.splitlines())

    # Step 3: Collapse multiple blank lines to 2 max
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Step 4: Render Markdown to HTML
    md = MarkdownIt("commonmark")  # or "zero" for minimal if you want strict control
    html = md.render(text)

    return html