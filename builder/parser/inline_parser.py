import re
from typing import List
from .ast_nodes import Node, Text, WikiLink, Image, WebLink, Italic, Bold, InlineCode

class InlineParser:
    # --- Regex Construction ---

    # 0. Inline Code: `text`
    inline_code_pattern = r'(`([^`]+)`)'

    # 1. Image embed: ![[path.png]] - MUST come before WikiLink
    image_pattern = r'(!\[\[(.+?)\]\])'

    # 2. WikiLink: [[Target]] or [[Target|Alias]]
    wikilink_pattern = r'(\[\[(.*?)(?:\|(.*?))?\]\])'

    # 3. Bold: __text__
    bold_pattern = r'(__(\S.+?)__)'

    # 4. Italic: *text*
    italic_star_pattern = r'(\*(.+?)\*)'

    # 5. Italic: _text_
    italic_underscore_pattern = r'(_(.+?)_)'

    # 6. Web Link: [alias](url)
    weblink_pattern = r'(\[([^\]]+)\]\(([^)]+)\))'

    # Combine and compile - ORDER MATTERS: image before wikilink
    TOKEN_RE = re.compile(f'{inline_code_pattern}|{image_pattern}|{wikilink_pattern}|{bold_pattern}|{italic_star_pattern}|{italic_underscore_pattern}|{weblink_pattern}')

    def parse(self, text: str) -> List[Node]:
        nodes = []
        last_pos = 0
        
        # Iterate through all regex matches in the string
        for match in self.TOKEN_RE.finditer(text):
            start, end = match.span()
            
            # 1. Plain text before the match
            if start > last_pos:
                text_chunk = text[last_pos:start]
                nodes.append(Text(text_chunk))
            
            # 2. Handle the match
            if match.group(1): # Inline Code
                content = match.group(2)
                code = InlineCode()
                code.add(Text(content))
                nodes.append(code)
            elif match.group(3): # Image
                src = match.group(4)
                nodes.append(Image(src))
            elif match.group(5): # WikiLink
                target = match.group(6)
                alias = match.group(7)
                nodes.append(WikiLink(target, alias))
            elif match.group(8): # Bold
                content = match.group(9)
                bold = Bold()
                bold.add(Text(content))
                nodes.append(bold)
            elif match.group(10): # Italic (star)
                content = match.group(11)
                italic = Italic()
                italic.add(Text(content))
                nodes.append(italic)
            elif match.group(12): # Italic (underscore)
                content = match.group(13)
                italic = Italic()
                italic.add(Text(content))
                nodes.append(italic)
            elif match.group(14): # Web Link
                alias = match.group(15)
                url = match.group(16)
                nodes.append(WebLink(url, alias))
            
            last_pos = end
            
        # 3. Remaining plain text after the last match
        if last_pos < len(text):
            nodes.append(Text(text[last_pos:]))
            
        return nodes
