from flask import Flask, request, redirect, url_for, render_template_string
import os
import subprocess
import tiktoken

app = Flask(__name__)
repo_name = ''
combined_code = ''


def count_tokens(text):
    enc = tiktoken.encoding_for_model("gpt-4o")
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
    combine_form = '''
    <form action="/combine" method="post">
        {checkboxes}
        <p id="totals">Total: 0 files, 0 bytes, 0 tokens</p>
        <input type="submit" value="Combine Files">
    </form>
    <form action="/delete" method="post">
        <input type="submit" value="Delete Repository">
    </form>
    <script>
    function updateTotals() {{
        var checkboxes = document.querySelectorAll('input[name="file_types"]:checked');
        var totalFiles = 0;
        var totalBytes = 0;
        var totalTokens = 0;
        var fileData = {file_types};
        checkboxes.forEach(function(checkbox) {{
            var ext = checkbox.value;
            totalFiles += fileData[ext]['count'];
            totalBytes += fileData[ext]['size'];
            totalTokens += fileData[ext]['tokens'];
        }});
        document.getElementById('totals').innerText = 'Total: ' + totalFiles + ' files, ' + totalBytes + ' bytes, ' + totalTokens + ' tokens';
    }}
    </script>
    <script>
    updateTotals();  // Update totals on initial load
    </script>
    '''

    if repo_name:
        file_types = get_file_types(repo_name)
        checkboxes = ''.join(
            f'<input type="checkbox" name="file_types" value="{ext}" checked onclick="updateTotals()"> {ext} ({info["count"]} files, {info["size"]} bytes, {info["tokens"]} tokens)<br>'
            for ext, info in file_types.items())
        return render_template_string(
            repo_form +
            combine_form.format(checkboxes=checkboxes, file_types=file_types))
    else:
        return render_template_string(repo_form)


def get_file_types(repo_name):
    file_types = {}
    for root, _, files in os.walk(repo_name):
        if '/.' in root:
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
    return file_types


@app.route('/clone', methods=['POST'])
def clone_repo():
    global repo_name
    url = request.form['url']
    repo_name = url.split('/')[-1].replace('.git', '')

    # Clone the repository if not already cloned
    if not os.path.exists(repo_name):
        clone_cmd = f'git clone {url} {repo_name}'
        subprocess.run(clone_cmd, shell=True)

    return redirect(url_for('home'))


@app.route('/combine', methods=['POST'])
def combine_files():
    global repo_name
    global combined_code
    include_file_types = request.form.getlist('file_types')

    # Combine all specified file types into one
    if os.path.exists(repo_name):
        os.chdir(repo_name)

        # Construct the find command with inclusions and exclude hidden directories
        find_command = "find . -type f ! -path '*/.*' \\( -name '*.json' -o -name '*.yml' -o -name '*.md' -o -name '*.ini' -o -name '*.py' -o -name '*.toml' -o -name '*.lock' -o -name '*.typed' -o -name '*.txt' \\) -exec sh -c 'echo \">>> FILE: $1 <<<\" && cat \"$1\"' sh {} \\; > ../all_code.txt"
        subprocess.run(find_command, shell=True, executable='/bin/bash')
        os.chdir('..')

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
    if os.path.exists(repo_name):
        subprocess.run(f'rm -rf {repo_name}', shell=True)
        repo_name = ''
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
