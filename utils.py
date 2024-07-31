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

def get_directory_structure(repo_path, file_data):
    def build_tree(path, info, tree):
        parts = path.split(os.sep)
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # File
                current[part] = info
            else:  # Directory
                if part not in current:
                    current[part] = {}
                current = current[part]

    tree = {}
    for path, info in file_data.items():
        build_tree(path, info, tree)

    def render_tree(node, path=''):
        if isinstance(node, dict):
            if 'size' in node and 'tokens' in node:  # File
                return f'<li><input type="checkbox" name="selected_files" value="{path}" checked> {os.path.basename(path)} ({node["size"]} bytes, {node["tokens"]} tokens)</li>'
            else:  # Directory
                if not node:  # Empty directory
                    return f'<li class="directory"><span class="toggle">+</span> {os.path.basename(path)}<ul style="display: none;"></ul></li>'
                content = ''.join(render_tree(v, os.path.join(path, k)) for k, v in node.items())
                if path:  # Not root
                    return f'<li class="directory"><span class="toggle">+</span> {os.path.basename(path)}<ul style="display: none;">{content}</ul></li>'
                return f'<ul>{content}</ul>'
        else:  # Unexpected type
            return f'<li>Error: Unexpected node type for {path}</li>'

    return render_tree(tree)

# def get_directory_structure(repo_path, file_data):
#     directory_structure = ''
#     dir_id = 0

#     def create_directory_structure(root, dirs, files, indent):
#         nonlocal dir_id
#         structure = ''
#         for d in dirs:
#             if d == '.git':
#                 continue
#             dir_id += 1
#             sub_dir_id = f"dir-{dir_id}"
#             structure += f'{indent}<input type="checkbox" name="selected_files" checked value="{os.path.join(root, d)}"> {d}/ <button type="button" hx-post="/toggle-directory" hx-target="#{sub_dir_id}" hx-swap="outerHTML">+</button><br>\n'
#             structure += f'<div id="{sub_dir_id}">\n'
#             sub_root = os.path.join(root, d)
#             sub_dirs = [
#                 sd for sd in os.listdir(sub_root)
#                 if os.path.isdir(os.path.join(sub_root, sd))
#                 and not sd.startswith('.')
#             ]
#             sub_files = [
#                 sf for sf in os.listdir(sub_root)
#                 if os.path.isfile(os.path.join(sub_root, sf))
#                 and not sf.startswith('.')
#             ]
#             structure += create_directory_structure(sub_root, sub_dirs,
#                                                     sub_files,
#                                                     indent + '&nbsp;' * 4)
#             structure += '</div>\n'
#         for f in files:
#             file_path = os.path.join(root, f)
#             file_info = file_data[file_path]
#             structure += f'{indent}<input type="checkbox" name="selected_files" value="{file_path}" checked> {f} ({file_info["size"]} bytes, {file_info["tokens"]} tokens)<br>\n'
#         return structure

#     for root, dirs, files in os.walk(repo_path):
#         if root == repo_path:
#             indent = '&nbsp;' * 4
#             directory_structure = create_directory_structure(
#                 root, dirs, files, indent)
#             break

#     return directory_structure
