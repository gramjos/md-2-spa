from abc import ABC, abstractmethod
import re
from typing import List, Optional, Any
from .ast_nodes import Node, Heading, CodeBlock, Paragraph, Text, ListNode, ListItem, FrontMatter

class LineReader:
    def __init__(self, lines: List[str]):
        self.lines = lines
        self.current_index = 0

    def peek(self) -> Optional[str]:
        if self.has_next():
            return self.lines[self.current_index]
        return None

    def next(self) -> Optional[str]:
        if self.has_next():
            line = self.lines[self.current_index]
            self.current_index += 1
            return line
        return None

    def has_next(self) -> bool:
        return self.current_index < len(self.lines)

class BlockProcessor(ABC):
    @abstractmethod
    def can_start(self, line: str) -> bool:
        pass

    @abstractmethod
    def run(self, parent: Node, reader: LineReader) -> Node:
        pass

class FrontMatterProcessor(BlockProcessor):
    def can_start(self, line: str) -> bool:
        return line.strip() == '---'

    def run(self, parent: Node, reader: LineReader) -> Node:
        reader.next() # Consume opening ---
        meta = {}
        
        while reader.has_next():
            line = reader.peek()
            if line is None:
                break
            
            if line.strip() == '---':
                reader.next() # Consume closing ---
                break
            
            content_line = reader.next()
            if ':' in content_line:
                key, value = content_line.split(':', 1)
                key = key.strip()
                value = value.strip()
                # check for 2 types of list notation tags:[value1, value2] or - value1(start new line)
                # if values is blank and the next line starts with '-', parse as list
                if not value and reader.has_next():
                    next_line = reader.peek()
                    if next_line and next_line.strip().startswith('-'):
                        list_values = []
                        while reader.has_next():
                            list_line = reader.peek()
                            if list_line is None or not list_line.strip().startswith('-'):
                                break
                            list_item = reader.next()
                            list_values.append(list_item.strip()[1:].strip())
                        meta[key] = list_values
                        continue
                meta[key] = self._parse_value(value)
        
        fm = FrontMatter(meta)
        parent.add(fm)
        return fm

    def _parse_value(self, value: str) -> Any:
        # List
        if value.startswith('[') and value.endswith(']'):
            inner = value[1:-1]
            # Handle empty list
            if not inner.strip():
                return []
            return [self._parse_value(v.strip()) for v in inner.split(',')]
        
        # Boolean
        if value == 'True': return True
        if value == 'False': return False
        
        # String with quotes
        if (value.startswith("'") and value.endswith("'")) or \
           (value.startswith('"') and value.endswith('"')):
            return value[1:-1]
            
        # Number
        if value.isdigit():
            return int(value)
            
        # Default string
        return value

class HeadingProcessor(BlockProcessor):
    def can_start(self, line: str) -> bool:
        return line.startswith('#')

    def run(self, parent: Node, reader: LineReader) -> Node:
        line = reader.next()
        if line is None:
            raise ValueError("Unexpected end of input in HeadingProcessor")
        
        level = 0
        for char in line:
            if char == '#':
                level += 1
            else:
                break
        
        level = min(max(level, 1), 6)
        content = line[level:].strip()
        
        heading = Heading(level)
        heading.add(Text(content))
        parent.add(heading)
        return heading

class CodeBlockProcessor(BlockProcessor):
    def can_start(self, line: str) -> bool:
        return line.strip().startswith('```')

    def run(self, parent: Node, reader: LineReader) -> Node:
        start_line = reader.next() # Consume the opening fence
        if start_line is None:
            raise ValueError("Unexpected end of input in CodeBlockProcessor")

        language = start_line.strip()[3:].strip()
        code_block = CodeBlock(language)
        
        code_content = []
        while reader.has_next():
            line = reader.peek()
            if line is None:
                break
                
            if line.strip().startswith('```'):
                reader.next() # Consume closing fence
                break
            
            # Consume the line
            content_line = reader.next()
            if content_line is not None:
                code_content.append(content_line)
            
        full_content = "\n".join(code_content)
        code_block.add(Text(full_content))
        parent.add(code_block)
        return code_block

class ListProcessor(BlockProcessor):
    LIST_PATTERN = re.compile(r'^(\s*)([-*+]|\d+\.)\s+(.*)')

    def can_start(self, line: str) -> bool:
        return bool(self.LIST_PATTERN.match(line))

    def run(self, parent: Node, reader: LineReader) -> Node:
        first_line = reader.peek()
        if not first_line:
            raise ValueError("Unexpected end of input in ListProcessor")

        match = self.LIST_PATTERN.match(first_line)
        if not match:
            raise ValueError("ListProcessor started on invalid line")
        
        marker = match.group(2)
        is_ordered = marker[0].isdigit()
        
        list_node = ListNode(ordered=is_ordered)
        
        while reader.has_next():
            line = reader.peek()
            if line is None:
                break
            
            # Check if empty line breaks list? 
            # Standard markdown: empty lines between items make it a "loose" list.
            # For now, let's stop on empty line or non-matching line.
            if not line.strip():
                break

            match = self.LIST_PATTERN.match(line)
            if not match:
                break
            
            current_marker = match.group(2)
            current_is_ordered = current_marker[0].isdigit()
            
            # If list type changes (ul <-> ol), break to start a new list block
            if current_is_ordered != is_ordered:
                break
                
            reader.next() # Consume the line
            content = match.group(3)
            
            item = ListItem()
            item.add(Text(content))
            list_node.add(item)
            
        parent.add(list_node)
        return list_node

class ParagraphProcessor(BlockProcessor):
    def can_start(self, line: str) -> bool:
        return line.strip() != ""

    def run(self, parent: Node, reader: LineReader) -> Node:
        paragraph = Paragraph()
        lines = []
        
        while reader.has_next():
            line = reader.peek()
            if line is None:
                break
            
            # Stop if we hit an empty line (paragraph break)
            if not line.strip():
                reader.next() # Consume the empty line
                break
                
            # Stop if we hit something that looks like another block
            if line.startswith('#') or line.strip().startswith('```'):
                break
                
            content_line = reader.next()
            if content_line is not None:
                lines.append(content_line)
            
        content = "\n".join(lines).strip()
        paragraph.add(Text(content))
        parent.add(paragraph)
        return paragraph
