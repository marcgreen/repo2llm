from fasthtml.common import *
from utils import get_file_types, get_directory_structure
import os
import subprocess
import logging
from typing import Optional
from starlette.responses import RedirectResponse
from starlette.requests import Request
from starlette.datastructures import State, FormData
from dataclasses import dataclass, asdict
import json

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

SUBDIRECTORY = 'cloned_repos'

@dataclass
class Repo:
    name: str
    path: str

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        return cls(**data)

    def __repr__(self):
        return f"Repo(name={self.name}, path={self.path})"
    
    def __str__(self):
        return self.path + '/' + self.name
    
app, rt = fast_app(
    hdrs=(
        picolink,
        Style(':root { --pico-font-size: 100%; }'),
        SortableJS('.sortable'),
        Script("""
            document.addEventListener('click', function(e) {
                if (e.target && e.target.classList.contains('toggle')) {
                    e.preventDefault();
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

            document.addEventListener('change', function(e) {
                if (e.target && e.target.classList.contains('directory-checkbox')) {
                    var li = e.target.closest('li');
                    var childCheckboxes = li.querySelectorAll('input[type="checkbox"]');
                    childCheckboxes.forEach(function(checkbox) {
                        checkbox.checked = e.target.checked;
                    });
                }
            });
        """)
    )
)

app.state.current_repo = None

def get_current_repo(request: Request) -> Optional[Repo]:
    repo = request.app.state.current_repo
    logging.debug(f"Current repo: {repo}")
    return repo

def render_directory_structure(structure, checked=True):
    if structure['type'] == 'file':
        if structure.get('skipped', False):
            return Li(
                f"{structure['name']} (Binary or unreadable file - skipped)",
                style="color: gray; font-style: italic;"
            )
        return Li(
            Checkbox(name="selected_files", value=structure['path'], checked=checked),
            f" {structure['name']} ({structure['size']} bytes, {structure['tokens']} tokens)"
        )
    else:
        children = [render_directory_structure(child, checked) for child in structure['children']]
        return Li(
            Checkbox(name="selected_files", value=structure['path'], checked=checked, cls="directory-checkbox"),
            Button("+", cls="toggle", type="button"),
            structure['name'],
            Ul(*children, style="display: none;")
        )
    
@rt("/")
async def get(request: Request):
    current_repo = get_current_repo(request)
    if current_repo:
        return render_repo_content(current_repo)
    else:
        return render_clone_form()

@rt("/clone")
async def post(request: Request, url: str):
    repo_name = url.split('/')[-1].replace('.git', '')
    repo_path = os.path.join(SUBDIRECTORY, repo_name)
    if not os.path.exists(repo_path):
        clone_cmd = f'git clone {url} {repo_path}'
        subprocess.run(clone_cmd, shell=True)
    request.app.state.current_repo = Repo(name=repo_name, path=repo_path)
    return RedirectResponse('/', status_code=303)

def calculate_totals(file_data, selected_files, excluded_file_types):
    total_files = 0
    total_bytes = 0
    total_tokens = 0

    exclude_no_extension = "(no extension)" in excluded_file_types
    excluded_file_types = [ext for ext in excluded_file_types if ext != "(no extension)"]

    for file_path in selected_files:
        if os.path.isdir(file_path):
            # If it's a directory, include all files under it
            for root, _, files in os.walk(file_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    if full_path in file_data:
                        _, ext = os.path.splitext(full_path)
                        if (ext or not exclude_no_extension) and not any(full_path.endswith(excluded_ext) for excluded_ext in excluded_file_types):
                            info = file_data[full_path]
                            total_files += info['count']
                            total_bytes += info['size']
                            total_tokens += info['tokens']
        elif file_path in file_data:
            _, ext = os.path.splitext(file_path)
            if (ext or not exclude_no_extension) and not any(file_path.endswith(excluded_ext) for excluded_ext in excluded_file_types):
                info = file_data[file_path]
                total_files += info['count']
                total_bytes += info['size']
                total_tokens += info['tokens']

    return total_files, total_bytes, total_tokens

@rt("/update-totals")
async def post(request: Request):
    logging.debug("update-totals route called")
    form_data = await request.form()
    excluded_file_types = form_data.getlist('file_types')
    selected_files = form_data.getlist('selected_files')
    
    current_repo = get_current_repo(request)
    if not current_repo:
        return {"error": "No repository selected"}, 400
    
    logging.debug(f"update_totals called with excluded_file_types: {excluded_file_types}, selected_files: {selected_files}")
    
    # Ensure all selected_files are relative to the repo path
    selected_files = [os.path.relpath(path, current_repo.path) for path in selected_files]
    
    _, file_data, _ = get_file_types(current_repo.path)
    total_files, total_bytes, total_tokens = calculate_totals(file_data, selected_files, excluded_file_types)

    result = f"Total: {total_files} files, {total_bytes} bytes, {total_tokens} tokens"
    logging.debug(f"Final result: {result}")
    return result

@rt("/combine")
async def post(request: Request):
    form_data = await request.form()
    file_types = form_data.getlist('file_types')
    selected_files = form_data.getlist('selected_files')
    
    current_repo = get_current_repo(request)
    if not current_repo:
        return {"error": "No repository selected"}, 400
    combined_code = ""

    for file_path in selected_files:
        full_path = os.path.join(current_repo.path, file_path)
        if os.path.exists(full_path) and not any(file_path.endswith(ext) for ext in file_types):
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                combined_code += f">>> FILE: {file_path} <<<\n{f.read()}\n\n"

    return Pre(combined_code)

@rt("/select-all")
async def post(request: Request):
    current_repo = get_current_repo(request)
    if not current_repo:
        return {"error": "No repository selected"}, 400
    _, file_data, skipped_files = get_file_types(current_repo.path)
    structure = get_directory_structure(current_repo.path, file_data, skipped_files)
    return render_directory_structure(structure)

@rt("/unselect-all")
async def post(request: Request):
    current_repo = get_current_repo(request)
    if not current_repo:
        return {"error": "No repository selected"}, 400
    _, file_data, skipped_files = get_file_types(current_repo.path)
    structure = get_directory_structure(current_repo.path, file_data, skipped_files)
    return render_directory_structure(structure, checked=False)

@rt("/delete")
async def post(request: Request):
    current_repo = get_current_repo(request)
    if not current_repo:
        return {"error": "No repository selected"}, 400
    if os.path.exists(current_repo.path):
        subprocess.run(f'rm -rf {current_repo.path}', shell=True)
    request.app.state.current_repo = None
    return RedirectResponse('/', status_code=303)

def render_clone_form():
    return Titled("Clone Repository",
        Form(
            Label("GitHub URL:", For="url"),
            Input(id='url', name='url', placeholder='https://github.com/user/repo.git'),
            Button('Clone Repository'),
            action='/clone', method='post'
        )
    )

def render_repo_content(repo: Repo):
    file_types, file_data, skipped_files = get_file_types(repo.path)
    structure = get_directory_structure(repo.path, file_data, skipped_files)
    dir_structure = render_directory_structure(structure)
    
    # Calculate initial totals
    all_files = list(file_data.keys())
    total_files, total_bytes, total_tokens = calculate_totals(file_data, all_files, [])
    
    # Sort file types, putting "(no extension)" at the end if it exists
    sorted_file_types = sorted(file_types.items(), key=lambda x: (x[0] != "(no extension)", x[0]))
    
    checkboxes = [
        Checkbox(name="file_types", value=ext, label=f"{ext} ({info['count']} files, {info['size']} bytes, {info['tokens']} tokens)")
        for ext, info in sorted_file_types
    ]
    
    return Titled(f"Repository: {repo.name}",
        Form(
            H3("File Type Exclusions"),
            Div(*checkboxes, id="file-types", hx_post="/update-totals", hx_trigger="change", hx_target="#totals"),
            P(f"Total: {total_files} files, {total_bytes} bytes, {total_tokens} tokens", id="totals"),
            H3("Directory Structure"),
            Div(
                Button("Select All", hx_post="/select-all", hx_target="#directory-structure"),
                Button("Unselect All", hx_post="/unselect-all", hx_target="#directory-structure")
            ),
            Div(dir_structure, 
                id="directory-structure", 
                hx_trigger="change", 
                hx_post="/update-totals", 
                hx_target="#totals",
                hx_include="[name='file_types'],[name='selected_files']"
            ),
            Button("Combine Files", type="submit"),
            action="/combine", method="post"
        ),
        Form(
            Button("Delete Repository"),
            action="/delete", method="post"
        )
    )

if __name__ == "__main__":
    serve()