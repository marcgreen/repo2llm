from flask import Flask, request, render_template_string, render_template, jsonify, current_app
import os
import logging
from utils import get_file_types, get_directory_structure
import subprocess

app = Flask(__name__)
app.config['SUBDIRECTORY'] = 'cloned_repos'
app.config['REPO_NAME'] = ''

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')


@app.route('/')
def home():
    if app.config['REPO_NAME']:
        return render_repo_content()
    else:
        content = '''
            <form hx-post="/clone" hx-target="#content">
                GitHub URL: <input type="text" name="url"><br>
                <input type="submit" value="Clone Repository">
            </form>
        '''
        return render_template_string('''
            {% extends "base.html" %}
            {% block content %}
            {{ content | safe }}
            {% endblock %}
        ''', content=content)


@app.route('/update-totals', methods=['POST'])
def update_totals():
    file_types = request.form.getlist('file_types')
    selected_files = request.form.getlist('selected_files')
    logging.debug(
        f"update_totals called with file_types: {file_types}, selected_files: {selected_files}"
    )

    total_files = 0
    total_bytes = 0
    total_tokens = 0

    repo_path = os.path.join(current_app.config['SUBDIRECTORY'],
                             current_app.config['REPO_NAME'])
    logging.debug(f"Repo path: {repo_path}")

    file_types_data, file_data = get_file_types(repo_path)
    logging.debug(f"File types data: {file_types_data}")
    logging.debug(f"File data: {file_data}")

    for file_path in selected_files:
        if file_path in file_data and not any(
                file_path.endswith(ext) for ext in file_types):
            info = file_data[file_path]
            total_files += info['count']
            total_bytes += info['size']
            total_tokens += info['tokens']
            logging.debug(
                f"Added file: {file_path}, new totals: {total_files} files, {total_bytes} bytes, {total_tokens} tokens"
            )

    result = f"Total: {total_files} files, {total_bytes} bytes, {total_tokens} tokens"
    logging.debug(f"Final result: {result}")
    return result


@app.route('/select-all', methods=['POST'])
def select_all():
    repo_path = os.path.join(current_app.config['SUBDIRECTORY'],
                             current_app.config['REPO_NAME'])
    logging.debug(f"select_all called for repo path: {repo_path}")
    _, file_data = get_file_types(repo_path)
    dir_structure = get_directory_structure(repo_path, file_data)
    result = dir_structure.replace('type="checkbox"',
                                   'type="checkbox" checked')
    logging.debug(f"select_all result: {result}")
    return jsonify({"html": result})


@app.route('/unselect-all', methods=['POST'])
def unselect_all():
    repo_path = os.path.join(current_app.config['SUBDIRECTORY'],
                             current_app.config['REPO_NAME'])
    logging.debug(f"unselect_all called for repo path: {repo_path}")
    _, file_data = get_file_types(repo_path)
    dir_structure = get_directory_structure(repo_path, file_data)
    result = dir_structure.replace(' checked', '')
    logging.debug(f"unselect_all result: {result}")
    return jsonify({"html": result})

def render_repo_content():
    file_types, file_data = get_file_types(
        os.path.join(app.config['SUBDIRECTORY'], app.config['REPO_NAME']))
    dir_structure = get_directory_structure(
        os.path.join(app.config['SUBDIRECTORY'], app.config['REPO_NAME']),
        file_data)
    checkboxes = ''.join(
        f'<input type="checkbox" name="file_types" value="{ext}" hx-post="/update-totals" hx-trigger="change" hx-target="#totals"> {ext} ({info["count"]} files, {info["size"]} bytes, {info["tokens"]} tokens)<br>'
        for ext, info in file_types.items())
    js_dir_toggle = '''
    <script>
        document.addEventListener('click', function(e) {
            if (e.target && e.target.className == 'toggle') {
                var content = e.target.parentElement.querySelector('ul');
                if (content.style.display === 'none') {
                    content.style.display = 'block';
                    e.target.textContent = '-';
                } else {
                    content.style.display = 'none';
                    e.target.textContent = '+';
                }
            }
        });
    </script>
    '''
    content='''
        {js_dir_toggle}
        <form hx-post="/combine" hx-target="#content">
            <h3>File Type Exclusions</h3>
            <div id="file-types" hx-trigger="change" hx-post="/update-totals" hx-target="#totals">
                {file_type_checkboxes}
            </div>
            <p id="totals">Total: 0 files, 0 bytes, 0 tokens</p>
            <input type="submit" value="Combine Files">
            <h3>Directory Structure</h3>
            <div>
                <button hx-post="/select-all" hx-target="#directory-structure">Select All</button>
                <button hx-post="/unselect-all" hx-target="#directory-structure">Unselect All</button>
            </div>
            <div id="directory-structure" hx-trigger="change" hx-post="/update-totals" hx-target="#totals">
                {directory_checkboxes}
            </div>
            <input type="submit" value="Combine Files">
        </form>
        <form hx-post="/delete" hx-target="#content">
            <input type="submit" value="Delete Repository">
        </form>
    '''.format(file_type_checkboxes=checkboxes,
               directory_checkboxes=dir_structure,
               js_dir_toggle=js_dir_toggle)
    return render_template('base.html', content=content)

@app.route('/clone', methods=['POST'])
def clone_repo():
    url = request.form['url']
    repo_name = url.split('/')[-1].replace('.git', '')

    repo_path = os.path.join(app.config['SUBDIRECTORY'], repo_name)
    if not os.path.exists(repo_path):
        clone_cmd = f'git clone {url} {repo_path}'
        subprocess.run(clone_cmd, shell=True)
    app.config['REPO_NAME'] = repo_name

    return render_template_string(render_repo_content())


@app.route('/combine', methods=['POST'])
def combine_files():
    global combined_code
    exclude_file_types = request.form.getlist('file_types')
    selected_files = request.form.getlist('selected_files')

    repo_path = os.path.join(app.config['SUBDIRECTORY'],
                             app.config['REPO_NAME'])
    combined_code = ""

    for file_path in selected_files:
        if not any(file_path.endswith(ext) for ext in exclude_file_types):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                combined_code += f">>> FILE: {file_path} <<<\n{f.read()}\n\n"

    return f'<pre>{combined_code}</pre>'


@app.route('/delete', methods=['POST'])
def delete_repo():
    repo_path = os.path.join(app.config['SUBDIRECTORY'],
                             app.config['REPO_NAME'])
    if os.path.exists(repo_path):
        subprocess.run(f'rm -rf {repo_path}', shell=True)
        app.config['REPO_NAME'] = ''
    return home()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
