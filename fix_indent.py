import os
import re

def fix_indentation_error():
    """Fix the indentation error in reels_maker.py"""
    file_path = '/app/app/reels_maker.py'
    
    print(f"Fixing indentation in {file_path}...")
    
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Process each line
        fixed_lines = []
        skip_next_lines = False
        
        for i, line in enumerate(lines):
            # If we're in a block we're removing, skip
            if skip_next_lines:
                if line.strip() and not line.startswith(' '):
                    skip_next_lines = False
                else:
                    continue
            
            # If this is the problematic line or related to metrics_logger
            if 'self.metrics_logger' in line:
                # Find if this is part of a method or block
                j = i - 1
                while j >= 0 and lines[j].strip() == '':
                    j -= 1
                
                # If it's an indented block (like inside __init__), remove the whole block
                if j >= 0 and (lines[j].strip().endswith(':') or 
                              'def __init__' in lines[j] or 
                              'if ' in lines[j] or 
                              'else:' in lines[j]):
                    skip_next_lines = True
                    continue
                
                # Otherwise skip just this line
                continue
            
            fixed_lines.append(line)
        
        # Write the fixed file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(fixed_lines)
        
        print("Fixed indentation errors.")
        
        # Additional fix for __init__ method
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix the __init__ method completely
        init_pattern = re.compile(r'def __init__.*?super\(\).__init__\(config\)', re.DOTALL)
        if init_pattern.search(content):
            new_content = init_pattern.sub(
                'def __init__(self, config: ReelsMakerConfig):\n        super().__init__(config)',
                content
            )
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("Successfully rewrote __init__ method.")
        
    except Exception as e:
        print(f"Error fixing indentation: {e}")

if __name__ == "__main__":
    fix_indentation_error()