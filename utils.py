import os
import tiktoken

def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-4")
    return len(enc.encode(text, disallowed_special=()))

def is_binary(file_path, chunk_size=8192):
    """
    Check if a file is binary by reading a chunk and looking for null bytes
    and other non-text characters.
    """
    try:
        with open(file_path, 'rb') as file:
            chunk = file.read(chunk_size)
            if b'\x00' in chunk:  # Check for null bytes
                return True
            # Check for a high percentage of non-text characters
            text_characters = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
            return float(len(chunk.translate(None, text_characters))) / len(chunk) > 0.30
    except IOError:
        return False
    
def get_file_types(repo_path):
    file_types = {}
    file_data = {}
    skipped_files = []
    for root, _, files in os.walk(repo_path):
        if root.endswith('.git'):
            continue
        for file in files:
            file_path = os.path.join(root, file)
            
            if is_binary(file_path):
                skipped_files.append(file_path)
                continue

            if file.startswith('.'):
                ext = file
            else:
                _, ext = os.path.splitext(file)
                if not ext:
                    ext = "(no extension)"
            
            try:
                size = os.path.getsize(file_path)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                tokens = count_tokens(content)
            except (UnicodeDecodeError, IOError):
                skipped_files.append(file_path)
                continue

            if ext in file_types:
                file_types[ext]['count'] += 1
                file_types[ext]['size'] += size
                file_types[ext]['tokens'] += tokens
            else:
                file_types[ext] = {'count': 1, 'size': size, 'tokens': tokens}
            file_data[file_path] = {'count': 1, 'size': size, 'tokens': tokens}
    
    return file_types, file_data, skipped_files

def get_directory_structure(path, file_data, skipped_files):
    name = os.path.basename(path)
    if os.path.isfile(path):
        if path in skipped_files:
            return {
                'type': 'file',
                'name': name,
                'path': path,
                'skipped': True
            }
        info = file_data.get(path, {})
        return {
            'type': 'file',
            'name': name,
            'path': path,
            'size': info.get('size', 0),
            'tokens': info.get('tokens', 0),
            'skipped': False
        }
    else:
        return {
            'type': 'directory',
            'name': name,
            'path': path,
            'children': [
                get_directory_structure(os.path.join(path, child), file_data, skipped_files)
                for child in os.listdir(path)
            ]
        }