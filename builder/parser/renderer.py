from .ast_nodes import Node, Document, Heading, Paragraph, Text, WikiLink, Image, WebLink, Italic, Bold, CodeBlock, ListNode, ListItem, InlineCode, FrontMatter
from .visitor import NodeVisitor
import os

class HTMLRenderer(NodeVisitor):
    def render(self, node: Node) -> str:
        """Entry point for the renderer."""
        return self.visit(node)

    def get_css(self) -> str:
        css_path = os.path.join(os.path.dirname(__file__), 'style.css')
        if os.path.exists(css_path):
            with open(css_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def visit_Document(self, node: Document) -> str:
        return "".join(self.visit(child) for child in node.children)

    def visit_FrontMatter(self, node: FrontMatter) -> str:
        # Front matter is metadata and usually not rendered to HTML body.
        # We can return an empty string or a comment.
        return ""

    def visit_Heading(self, node: Heading) -> str:
        content = self._render_children(node)
        return f"<h{node.level}>{content}</h{node.level}>"

    def visit_Paragraph(self, node: Paragraph) -> str:
        content = self._render_children(node)
        return f"<p>{content}</p>"

    def visit_Text(self, node: Text) -> str:
        text = node.content or ""
        return text.replace("\n", "<br>")

    def visit_WikiLink(self, node: WikiLink) -> str:
        display_text = node.alias if node.alias else node.target
        return f'<a href="{node.target}">{display_text}</a>'

    def visit_Image(self, node: Image) -> str:
        return f'<img src="graphics/{node.src}" alt="{node.src}">'

    def visit_WebLink(self, node: WebLink) -> str:
        url = node.url
        # Ensure URL has a protocol, default to https
        if url and not url.startswith(('http://', 'https://', 'mailto:', '/')):
            url = f'https://{url}'
        return f'<a href="{url}" target="_blank" rel="noopener">{node.alias}</a>'

    def visit_Italic(self, node: Italic) -> str:
        content = self._render_children(node)
        return f"<em>{content}</em>"

    def visit_Bold(self, node: Bold) -> str:
        content = self._render_children(node)
        return f"<strong>{content}</strong>"

    def visit_CodeBlock(self, node: CodeBlock) -> str:
        content = self._render_children(node)
        # Escape HTML entities if needed, but for now just wrap
        class_attr = f' class="language-{node.language}"' if node.language else ""
        return f'<pre><code{class_attr}>{content}</code></pre>'

    def visit_ListNode(self, node: ListNode) -> str:
        content = self._render_children(node)
        tag = "ol" if node.ordered else "ul"
        return f"<{tag}>{content}</{tag}>"

    def visit_ListItem(self, node: ListItem) -> str:
        content = self._render_children(node)
        return f"<li>{content}</li>"

    def visit_InlineCode(self, node: InlineCode) -> str:
        content = self._render_children(node)
        return f"<code>{content}</code>"

    def generic_visit(self, node: Node) -> str:
        # Fallback for unimplemented nodes (like Lists/BlockQuotes if they appear)
        return self._render_children(node)

    def _render_children(self, node: Node) -> str:
        """Helper to visit all children and join their results."""
        return "".join(self.visit(child) for child in node.children)
