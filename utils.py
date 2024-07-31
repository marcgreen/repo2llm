import os
import tiktoken

def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-4")
    return len(enc.encode(text, disallowed_special=()))

def get_file_types(repo_path):
    file_types = {}
    file_data = {}
    skipped_files = []
    for root, _, files in os.walk(repo_path):
        if root.endswith('.git'):
            continue
        for file in files:
            file_path = os.path.join(root, file)
            
            if file.startswith('.'):
                ext = file
            else:
                _, ext = os.path.splitext(file)
                if not ext:
                    ext = "(no extension)"
            
            try:
                size = os.path.getsize(file_path)
                with open(file_path, 'rb') as f:
                    content = f.read()
                try:
                    content = content.decode('utf-8')
                    tokens = count_tokens(content)
                except UnicodeDecodeError:
                    skipped_files.append(file_path)
                    continue
            except IOError:
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