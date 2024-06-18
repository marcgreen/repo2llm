from flask import Flask, request, redirect, url_for, render_template_string
import os
import subprocess
import tiktoken
import json

app = Flask(__name__)
repo_name = ''
subdirectory = 'cloned_repos'
combined_code = ''

# Ensure the subdirectory exists
os.makedirs(subdirectory, exist_ok=True)


def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-4")
    return len(enc.encode(text, disallowed_special=()))


@app.route('/')
def home():
    global repo_name
    repo_form = '''
    <form action="/clone" method="post">
        GitHub URL: <input type="text" name="url"><br>
        <input type="submit" value="Clone Repository">
    </form>
    '''
    if repo_name:
        file_types, file_data = get_file_types(
            os.path.join(subdirectory, repo_name))
        dir_structure = get_directory_structure(
            os.path.join(subdirectory, repo_name), file_data)
        checkboxes = ''.join(
            f'<input type="checkbox" name="file_types" value="{ext}" onclick="updateTotals()"> {ext} ({info["count"]} files, {info["size"]} bytes, {info["tokens"]} tokens)<br>'
            for ext, info in file_types.items())

        return render_template_string('''
            <form action="/combine" method="post">
                <h3>File Type Exclusions</h3>
                {file_type_checkboxes}
                <p id="totals">Total: 0 files, 0 bytes, 0 tokens</p>
                <input type="submit" value="Combine Files">
                <h3>Directory Structure</h3>
                <div>
                    <button type="button" onclick="selectAll()">Select All</button>
                    <button type="button" onclick="unselectAll()">Unselect All</button>
                </div>
                {directory_checkboxes}
                <input type="submit" value="Combine Files">
            </form>
            <form action="/delete" method="post">
                <input type="submit" value="Delete Repository">
            </form>
            <script>
            function updateTotals() {{
                var totalFiles = 0;
                var totalBytes = 0;
                var totalTokens = 0;
                var fileData = {file_data};
                var excludedFileTypes = Array.from(document.querySelectorAll('input[name="file_types"]:checked')).map(cb => cb.value);

                var checkboxes = document.querySelectorAll('input[name="selected_files"]:checked');
                checkboxes.forEach(function(checkbox) {{
                    var file = checkbox.value;
                    if (fileData[file] && !excludedFileTypes.some(ext => file.endsWith(ext))) {{
                        totalFiles += fileData[file].count;
                        totalBytes += fileData[file].size;
                        totalTokens += fileData[file].tokens;
                    }}
                }});
                document.getElementById('totals').innerText = 'Total: ' + totalFiles + ' files, ' + totalBytes + ' bytes, ' + totalTokens + ' tokens';
            }}

            function toggleDirectory(button) {{
                var target = document.getElementById(button.dataset.target);
                if (target.style.display === 'none') {{
                    target.style.display = 'block';
                    button.innerText = '-';
                }} else {{
                    target.style.display = 'none';
                    button.innerText = '+';
                }}
                // Update the state of all nested checkboxes
                var checkbox = button.previousElementSibling;
                var isChecked = checkbox.checked;
                toggleCheckboxes(target, isChecked);
                updateTotals();  // Update totals when a directory is toggled
            }}

            function toggleCheckboxes(parent, isChecked) {{
                var checkboxes = parent.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(function(checkbox) {{
                    checkbox.checked = isChecked;
                }});
            }}

            function selectAll() {{
                var checkboxes = document.querySelectorAll('input[name="selected_files"]');
                checkboxes.forEach(function(checkbox) {{
                    checkbox.checked = true;
                }});
                updateTotals();
            }}

            function unselectAll() {{
                var checkboxes = document.querySelectorAll('input[name="selected_files"]');
                checkboxes.forEach(function(checkbox) {{
                    checkbox.checked = false;
                }});
                updateTotals();
            }}

            function toggleCheckbox(checkbox, targetId) {{
                var isChecked = checkbox.checked;
                var target = document.getElementById(targetId);
                var checkboxes = target.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(function(childCheckbox) {{
                    childCheckbox.checked = isChecked;
                }});
                updateTotals();  // Update totals when a directory checkbox is toggled
            }}

            document.querySelectorAll('input[name="file_types"]').forEach(cb => {{
                cb.addEventListener('change', updateTotals);
            }});

            document.querySelectorAll('input[name="selected_files"]').forEach(cb => {{
                cb.addEventListener('change', updateTotals);
            }});

            


            window.onload = updateTotals;  // Update totals on initial load
            </script>
            '''.format(file_type_checkboxes=checkboxes,
                       directory_checkboxes=dir_structure,
                       file_data=json.dumps(file_data)))
    else:
        return render_template_string(repo_form)


def get_file_types(repo_path):
    file_types = {}
    file_data = {}
    for root, _, files in os.walk(repo_path):
        # Skip hidden directories and files and the .git directory
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
    directory_structure = ''
    dir_id = 0

    def create_directory_structure(root, dirs, files, indent):
        nonlocal dir_id
        structure = ''
        for d in dirs:
            if d == '.git':
                continue
            dir_id += 1
            sub_dir_id = f"dir-{dir_id}"
            structure += f'{indent}<input type="checkbox" name="selected_files" checked value="{os.path.join(root, d)}" onclick="toggleCheckbox(this, \'{sub_dir_id}\')"> {d}/ <button type="button" onclick="toggleDirectory(this)" data-target="{sub_dir_id}">+</button><br>\n'
            structure += f'<div id="{sub_dir_id}" style="display:none;">\n'
            sub_root = os.path.join(root, d)
            sub_dirs = [
                sd for sd in os.listdir(sub_root)
                if os.path.isdir(os.path.join(sub_root, sd))
                and not sd.startswith('.')
            ]
            sub_files = [
                sf for sf in os.listdir(sub_root)
                if os.path.isfile(os.path.join(sub_root, sf))
                and not sf.startswith('.')
            ]
            structure += create_directory_structure(sub_root, sub_dirs,
                                                    sub_files,
                                                    indent + '&nbsp;' * 4)
            structure += '</div>\n'
        for f in files:
            file_path = os.path.join(root, f)
            file_info = file_data[file_path]
            structure += f'{indent}<input type="checkbox" name="selected_files" value="{file_path}" data-path="{file_path}" checked onclick="updateTotals()"> {f} ({file_info["size"]} bytes, {file_info["tokens"]} tokens)<br>\n'
        return structure

    for root, dirs, files in os.walk(repo_path):
        if root == repo_path:
            indent = '&nbsp;' * 4
            directory_structure = create_directory_structure(
                root, dirs, files, indent)
            break

    return directory_structure


@app.route('/clone', methods=['POST'])
def clone_repo():
    global repo_name
    url = request.form['url']
    repo_name = url.split('/')[-1].replace('.git', '')

    # Clone the repository if not already cloned
    repo_path = os.path.join(subdirectory, repo_name)
    if not os.path.exists(repo_path):
        clone_cmd = f'git clone {url} {repo_path}'
        subprocess.run(clone_cmd, shell=True)

    return redirect(url_for('home'))


@app.route('/combine', methods=['POST'])
def combine_files():
    global repo_name
    global combined_code
    exclude_file_types = request.form.getlist('file_types')
    selected_files = request.form.getlist('selected_files')

    # Exclude selected file types
    exclude_patterns = " -o ".join(
        [f"-name '*{file_type}'" for file_type in exclude_file_types])
    print(exclude_file_types)
    print(exclude_patterns)

    repo_path = os.path.join(subdirectory, repo_name)
    if os.path.exists(repo_path):
        os.chdir(repo_path)

        # Construct the find command to include selected files and exclude specified file types
        # exclude_str = f"\\( {exclude_patterns} \\)" if exclude_patterns else ""
        # find_command = f"find . -type f ! -path '*/.*' {exclude_str} -prune -o -type f \\( " + " -o ".join(
        #     [f"-path '{os.path.relpath(file, repo_path)}'" for file in selected_files]
        # ) + f" \\) -exec sh -c 'echo \">>> FILE: $1 <<<\" && cat \"$1\"' sh {{}} \\; > ../../all_code.txt"
        find_command = (
            f"find . " + (f"\\( -type f {exclude_patterns} -prune \\) -o"
                          if exclude_patterns else "") + " -type f \\( " +
            " -o ".join([
                f"-path './{os.path.relpath(file, repo_path)}'"
                for file in selected_files
            ]) +
            f" \\) -exec sh -c 'echo \">>> FILE: $1 <<<\" && cat \"$1\"' sh {{}} \\; > ../../all_code.txt"
        )
        print(find_command)
        subprocess.run(find_command, shell=True, executable='/bin/bash')
        os.chdir('../..')

        # Read the combined file and store it in a global variable
        with open('all_code.txt', 'r') as file:
            combined_code = file.read()

        # Clean up the combined file
        subprocess.run('rm all_code.txt', shell=True)

        return redirect(url_for('display_combined_code'))

    else:
        return 'Repository not found. Please clone the repository first.'


@app.route('/display_combined_code', methods=['GET'])
def display_combined_code():
    global combined_code
    return f'<pre>{combined_code}</pre>'


@app.route('/delete', methods=['POST'])
def delete_repo():
    global repo_name
    repo_path = os.path.join(subdirectory, repo_name)
    if os.path.exists(repo_path):
        subprocess.run(f'rm -rf {repo_path}', shell=True)
        repo_name = ''
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
