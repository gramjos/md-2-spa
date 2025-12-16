from pathlib import Path
from .md_parser import Parser
from .renderer import HTMLRenderer

def main():
    # Resolve paths relative to this script's location
    script_dir = Path(__file__).parent
    input_markdown = (script_dir / "sample.md").read_text(encoding="utf-8")
    
    # 1. Parse
    parser = Parser()
    print(f"The in... {input_markdown=}")
    doc = parser.parse(input_markdown)
    
    print("Parsed AST:")
    print(doc)
    print("-" * 20)
    print(doc.pretty())
    print("-" * 20)

    # 2. Render
    renderer = HTMLRenderer()
    html = renderer.render(doc)
    
    print("Generated HTML:")
    print(html)

    output_file = script_dir / "sample.html"
    output_file.write_text( html, encoding="utf-8")
    print(f"Successfully wrote HTML to {output_file}")

if __name__ == "__main__":
    main()
