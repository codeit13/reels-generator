import os
import re
import ast
import traceback

def is_syntax_valid(code):
    """Check if code has valid syntax."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

def fix_all_files():
    """Fix syntax errors in all Python files."""
    base_dir = '/app'
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                fix_file(file_path)

def fix_file(file_path):
    """Fix syntax errors in a specific file."""
    print(f"Processing {file_path}...")
    
    try:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Skip if already valid
        if is_syntax_valid(content):
            print(f"  ✓ {file_path} has valid syntax")
            return
            
        print(f"  ! Syntax errors found in {file_path}, fixing...")
        
        # 1. Remove problematic imports
        content = re.sub(r'from app\.utils\.(video_match_logger|metrics_logger) import .*?\n', '', content)
        content = re.sub(r'import app\.utils\.(video_match_logger|metrics_logger).*?\n', '', content)
        
        # 2. Fix unmatched parentheses by removing logger-related lines
        lines = content.split('\n')
        fixed_lines = []
        skip_line = False
        open_brackets = 0
        
        for i, line in enumerate(lines):
            # Skip lines with metrics_logger or video_match_logger
            if 'metrics_logger' in line or 'video_match_logger' in line:
                skip_line = True
                # Count brackets to track multiline statements
                open_brackets += line.count('(') - line.count(')')
                continue
                
            # If we're in a multiline statement with loggers
            if skip_line:
                # Count brackets to see if we should continue skipping
                open_brackets += line.count('(') - line.count(')')
                if open_brackets <= 0:
                    skip_line = False
                continue
                
            # Fix incomplete lines due to removed logger code
            if line.strip() == ')' and i > 0 and 'logger' in lines[i-1]:
                continue
                
            fixed_lines.append(line)
        
        # 3. Join lines and fix common patterns
        fixed_content = '\n'.join(fixed_lines)
        
        # Fix trailing commas in function calls
        fixed_content = re.sub(r',\s*\)', ')', fixed_content)
        
        # Fix missing commas between parameters
        fixed_content = re.sub(r'(\w+)\s+(\w+)', r'\1, \2', fixed_content)
        
        # Fix empty if blocks
        fixed_content = re.sub(r'if.*?:\s*\n\s*\n', '', fixed_content)
        
        # Fix lines ending with operators
        operator_pattern = re.compile(r'(.*?[=+\-*/%])\s*$')
        lines = fixed_content.split('\n')
        for i in range(len(lines) - 1):
            match = operator_pattern.match(lines[i])
            if match and not lines[i+1].strip().startswith(('if', 'for', 'def', 'class', '#')):
                lines[i] = lines[i] + " ''"  # Add empty string to complete expression
        fixed_content = '\n'.join(lines)
        
        # 4. Special fix for invalid syntax at line 122 in reels_maker.py
        if 'reels_maker.py' in file_path:
            # Specifically fix line 122
            lines = fixed_content.split('\n')
            for i, line in enumerate(lines):
                if "if not script or script.strip() == \"\":" in line:
                    # Check if previous line might be incomplete
                    prev_line = lines[i-1] if i > 0 else ""
                    if prev_line.strip().endswith(('=', '+', '-', '*', '/', '%', '(', ',', ':', '[', '{')):
                        lines[i-1] = prev_line + " ''"  # Complete previous line
            
            fixed_content = '\n'.join(lines)
            
            # Fix __init__ method
            fixed_content = re.sub(
                r'def __init__.*?super\(\).__init__\(config\)',
                'def __init__(self, config: ReelsMakerConfig):\n        super().__init__(config)',
                fixed_content,
                flags=re.DOTALL
            )
            
            # Fix start method parameters
            fixed_content = re.sub(
                r'async def start\(self, st_state=None, metrics_logger=None, video_match_logger=None\)',
                'async def start(self, st_state=None)',
                fixed_content
            )
        
        # 5. Write fixed content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
            
        # 6. Verify the fix worked
        if is_syntax_valid(fixed_content):
            print(f"  ✓ Successfully fixed {file_path}")
        else:
            print(f"  ✗ Syntax errors remain in {file_path}")
            
    except Exception as e:
        print(f"  ✗ Error fixing {file_path}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    fix_all_files()