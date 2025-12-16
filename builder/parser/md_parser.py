from typing import List
from .ast_nodes import Document, Node, Text
from .inline_parser import InlineParser
from .block_processors import LineReader, HeadingProcessor, CodeBlockProcessor, ParagraphProcessor, BlockProcessor, ListProcessor, FrontMatterProcessor

class Parser:
    def __init__(self):
        self.inline_parser = InlineParser()
        self.front_matter_processor = FrontMatterProcessor()
        self.processors: List[BlockProcessor] = [
            HeadingProcessor(),
            CodeBlockProcessor(),
            ListProcessor(),
            ParagraphProcessor()
        ]

    def parse(self, text: str) -> Document:
        doc = Document()
        lines = text.split('\n')
        reader = LineReader(lines)
        
        # Check for Front Matter at the very beginning
        if reader.has_next() and self.front_matter_processor.can_start(reader.peek()):
            self.front_matter_processor.run(doc, reader)
        
        while reader.has_next():
            line = reader.peek()
            if line is None:
                break
                
            # Skip empty lines at the top level
            if not line.strip():
                reader.next()
                continue
            
            matched = False
            for processor in self.processors:
                if processor.can_start(line):
                    processor.run(doc, reader)
                    matched = True
                    break
            
            if not matched:
                # Should not happen if ParagraphProcessor is configured correctly as fallback
                # for non-empty lines. But to be safe and avoid infinite loops:
                reader.next()
        
        # --- PASS 2: Inline Parsing ---
        self._process_inline_elements(doc)
                
        return doc

    def _process_inline_elements(self, node: Node):
        """
        Recursively walks the tree. 
        If it finds a Text node, it runs the inline parser and expands it.
        """
        new_children = []
        
        for child in node.children:
            # If we hit a leaf Text node, explode it!
            if isinstance(child, Text):
                content = child.content if child.content is not None else ""
                parsed_nodes = self.inline_parser.parse(content)
                new_children.extend(parsed_nodes)
            else:
                # If it's a block (Heading/Paragraph), recurse deeper
                self._process_inline_elements(child)
                new_children.append(child)
        
        node.children = new_children
