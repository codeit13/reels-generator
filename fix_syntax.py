import os
import re

def fix_syntax_errors():
    """Fix syntax errors in reels_maker.py"""
    file_path = '/app/app/reels_maker.py'
    
    print(f"Fixing syntax errors in {file_path}...")
    
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 1. Fix unmatched parenthesis by first removing all metrics logger lines
        # This handles both standalone calls and incomplete parts of larger expressions
        lines = content.split('\n')
        fixed_lines = []
        
        in_multiline_statement = False
        parenthesis_count = 0
        
        for line in lines:
            # Skip lines with metrics_logger or incomplete calls
            if 'metrics_logger' in line or 'video_match_logger' in line:
                continue
                
            # Handle incomplete lines with just closing parenthesis
            if line.strip() == ')':
                if in_multiline_statement and parenthesis_count > 0:
                    parenthesis_count -= 1
                    if parenthesis_count == 0:
                        in_multiline_statement = False
                    fixed_lines.append(line)
                # Skip lone closing parenthesis that aren't part of tracked statements
                continue
                
            # Count opening and closing parentheses to track multiline statements
            open_count = line.count('(')
            close_count = line.count(')')
            
            if open_count > close_count:
                in_multiline_statement = True
                parenthesis_count += (open_count - close_count)
            elif close_count > open_count and parenthesis_count > 0:
                parenthesis_count -= (close_count - open_count)
                if parenthesis_count == 0:
                    in_multiline_statement = False
            
            fixed_lines.append(line)
        
        # 2. Fix extremely common patterns of broken expressions from metrics logger removal
        new_content = '\n'.join(fixed_lines)
        
        # Fix multi-line parameter lists with metrics_logger
        new_content = re.sub(r',\s*\n\s*\)', ')', new_content)
        
        # Fix expressions of form: '...\n    )'
        new_content = re.sub(r'\n\s*\)', ')', new_content)
        
        # Fix empty if statements
        new_content = re.sub(r'if.*?:\s*\n\s*\n', '', new_content)
        
        # Fix trailing commas in function calls
        new_content = re.sub(r',\s*\)', ')', new_content)
        
        # 3. Fix __init__ method completely
        new_content = re.sub(
            r'def __init__.*?super\(\).__init__\(config\)',
            'def __init__(self, config: ReelsMakerConfig):\n        super().__init__(config)',
            new_content,
            flags=re.DOTALL
        )
        
        # 4. Fix start method parameters
        new_content = re.sub(
            r'async def start\(self, st_state=None, metrics_logger=None, video_match_logger=None\)',
            'async def start(self, st_state=None)',
            new_content
        )
        
        # Write the fixed content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("Fixed syntax errors in reels_maker.py")
        
        # Also clean up imports
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = re.sub(r'from app\.utils\.video_match_logger import VideoMatchLogger\n', '', content)
        content = re.sub(r'from app\.utils\.metrics_logger import MetricsLogger\n', '', content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("Removed logger imports")
        
    except Exception as e:
        print(f"Error fixing syntax: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_syntax_errors()