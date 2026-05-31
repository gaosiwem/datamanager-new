from django.template import Context, Template
from django.test import SimpleTestCase


class MarkdownRenderingTestCase(SimpleTestCase):
    def render_intro(self, text):
        template = Template(
            "{% load markdownify markdown_extras %}"
            "{{ text|ensure_heading_blocks|markdownify|safe }}"
        )
        return template.render(Context({"text": text}))

    def test_headings_and_lists_render_from_markdown(self):
        rendered = self.render_intro("# Heading\n\n- item")

        self.assertIn("<h1>Heading</h1>", rendered)
        self.assertIn("<li>item</li>", rendered)
        self.assertNotIn("># Heading<", rendered)

    def test_literal_newlines_are_normalized_before_markdownify(self):
        rendered = self.render_intro("Intro\\n\\n## Section")

        self.assertIn("<p>Intro</p>", rendered)
        self.assertIn("<h2>Section</h2>", rendered)
