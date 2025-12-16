# Obsidian Markdown to HTML

## Parsing Rules
### Block
- **Headings**: Starts with `#` (1-6).
- **Code Blocks**: Delimited by triple backticks (\`\`\`).
- **Paragraphs**: Consecutive lines of text.
- **Front Matter**: Leading meta data.

### Inline (Precedence Order)
The parser evaluates inline elements in the following order:
1. **WikiLinks**: `[[Target]]` or `[[Target|Alias]]`
2. **Bold**: `__text__` (Double underscore)
3. **Italic**: `*text*` (Star) or `_text_` (Single underscore)
4. **Images**: `![[...]]` where `...` is a path to a asset: gif, png, jpeg, jpg
5. **Web Links**: `[alias](url)` 

## Creating a New Parsing Rule

When adding a new feature to the parser, ask yourself these questions to determine the implementation path:

1.  **Is the element a Block or Inline?**
    *   *Does it consume entire lines (like a Quote or List)?* &rarr; It's a **Block**.
    *   *Does it exist inside a paragraph (like a Highlight or Link)?* &rarr; It's **Inline**.

2.  Define a new dataclass in `ast_nodes.py` (e.g., `class BlockQuote(Node)`). Don't forget to add it to the `NodeType` enum.

3.  **If it's a Block...**
    *   *How do I identify the start of the block?* &rarr; Implement `can_start(line)` in a new `BlockProcessor` subclass in `block_processors.py`.
    *   *How do I consume the content?* &rarr; Implement `run(parent, reader)` to consume lines from `LineReader` and attach the new Node to the parent.
    *   *Does order matter?* &rarr; Yes. Register your new processor in `md_parser.py`. If it clashes with Paragraphs or other blocks, place it higher in the `self.processors` list.

4.  **If it's Inline...**
    *   *What does it look like?* &rarr; Define a Regex pattern in `inline_parser.py`.
    *   *Does it conflict with other patterns?* &rarr; Add it to `TOKEN_RE`. Remember: **Order matters**. Specific patterns (like `__bold__`) must come before generic ones (like `_italic_`) if they share characters.

5.  **How does it look in HTML?**
    *   *How should the renderer handle the new Node?* &rarr; Add a `visit_NewNodeName(self, node)` method in `renderer.py` to return the HTML string.

### `ctags`
```zsh
ctags -R --languages=Python \
  --exclude=.git \
  --exclude=.venv \
  --exclude=__pycache__ \
  --exclude=build \
  --exclude=dist \
  --exclude='*.egg-info' \
  --exclude=output_html \
  --exclude=test_data
```

## Usage
To run the parser on the sample input:
```bash
python3 main.py
```

To run the batch converter:
```bash
python3 batch_converter.py
```

## Technical Notes:
Dataclasses:
	Default factory:

```python
@dataclass
class Node:
    type: NodeType
    children: List['Node'] = []
	# the above is wrong because when `Node` is initialized the same reference for `children` will shared across isntances of `Node`
	# `field(default_factory=list)` Is use to created a fresh new children's list for every instance of `Node` 
    children: List['Node'] = field(default_factory=list)
```
