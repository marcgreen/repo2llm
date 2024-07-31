import os
import tiktoken

def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-4")
    return len(enc.encode(text, disallowed_special=()))

def get_file_types(repo_path):
    file_types = {}
    file_data = {}
    for root, _, files in os.walk(repo_path):
        if root.endswith('.git'):
            continue
        for file in files:
            ext = os.path.splitext(file)[1]
            file_path = os.path.join(root, file)
            size = os.path.getsize(file_path)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tokens = count_tokens(content)
            if ext in file_types:
                file_types[ext]['count'] += 1
                file_types[ext]['size'] += size
                file_types[ext]['tokens'] += tokens
            else:
                file_types[ext] = {'count': 1, 'size': size, 'tokens': tokens}
            file_data[file_path] = {'count': 1, 'size': size, 'tokens': tokens}
    return file_types, file_data

import os

def get_directory_structure(path, file_data):
    name = os.path.basename(path)
    if os.path.isfile(path):
        info = file_data.get(path, {})
        return {
            'type': 'file',
            'name': name,
            'path': path,
            'size': info.get('size', 0),
            'tokens': info.get('tokens', 0)
        }
    else:
        return {
            'type': 'directory',
            'name': name,
            'path': path,
            'children': [
                get_directory_structure(os.path.join(path, child), file_data)
                for child in os.listdir(path)
                if not child.startswith('.')  # Skip hidden files/directories
            ]
        }