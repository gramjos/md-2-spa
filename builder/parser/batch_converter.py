from pathlib import Path
from typing import List
import os
from md_parser import Parser
from renderer import HTMLRenderer

def convert_all(input_dir: str, output_dir: str):
    'input_dir: str, output_dir: str'

    input_path = Path(input_dir).expanduser()
    output_path = Path(output_dir).expanduser()
    
    # Ensure output directory exists
    output_path.mkdir(parents=True, exist_ok=True)
    
    parser = Parser()
    renderer = HTMLRenderer()
    
    print(f"Scanning {input_path} for markdown files...")
    
    files_processed = 0
    for root, dirs, files in os.walk(input_path):
        # Modify dirs in-place to skip unwanted directories
        dirs[:] = [d for d in dirs if d not in {".obsidian", ".git"}]
        
        if not any(f.lower() == 'readme.md' for f in files): # Flag check: Only process directory if README.md exists (case-insensitive)
            continue
            
        root_path = Path(root)
        
        for file in sorted(files):
            if not file.endswith(".md"):
                continue
                
            md_file = root_path / file
            rp = md_file.relative_to(input_path)
            print(f"Processing {rp}...")
            
            # Read Markdown
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse and Render
            doc = parser.parse(content)
            html_content = renderer.render(doc)
            
            # Wrap in a basic HTML structure for better viewing
            # full_html = f"""<!DOCTYPE html>
# <html>
# <head>
    # <title>{md_file.stem}</title>
    # <style>
        # {renderer.get_css()}
    # </style>
# </head>
# <body>
    # {html_content}
# </body>
# </html>"""
            # just html
            full_html = html_content            
            # Write HTML
            relative_path = md_file.relative_to(input_path)
            output_file = output_path / relative_path.with_suffix('.html')
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(full_html)
                
            files_processed += 1
        
    print(f"Done! Processed {files_processed} files. Check {output_path} for results.")

if __name__ == "__main__":
    # You can configure these paths
    INPUT_DIR = "~/Obsidian_Vault"
    OUTPUT_DIR = "output_html"
    
    convert_all(INPUT_DIR, OUTPUT_DIR)
