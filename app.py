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
        return Li(
            Checkbox(name="selected_files", value=structure['path'], checked=checked),
            f" {structure['name']} ({structure['size']} bytes, {structure['tokens']} tokens)"
        )
    else:
        children = [render_directory_structure(child, checked) for child in structure['children']]
        return Li(
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

@rt("/update-totals")
async def post(request: Request):
    logging.debug("update-totals route called")
    form_data = await request.form()
    file_types = form_data.getlist('file_types')
    selected_files = form_data.getlist('selected_files')
    
    current_repo = get_current_repo(request)
    if not current_repo:
        return {"error": "No repository selected"}, 400
    
    logging.debug(f"update_totals called with file_types: {file_types}, selected_files: {selected_files}")
    
    total_files = 0
    total_bytes = 0
    total_tokens = 0

    _, file_data = get_file_types(current_repo.path)

    for file_path in selected_files:
        if file_path in file_data and not any(file_path.endswith(ext) for ext in file_types):
            info = file_data[file_path]
            total_files += info['count']
            total_bytes += info['size']
            total_tokens += info['tokens']

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
    _, file_data = get_file_types(current_repo.path)
    structure = get_directory_structure(current_repo.path, file_data)
    return render_directory_structure(structure)

@rt("/unselect-all")
async def post(request: Request):
    current_repo = get_current_repo(request)
    if not current_repo:
        return {"error": "No repository selected"}, 400
    _, file_data = get_file_types(current_repo.path)
    structure = get_directory_structure(current_repo.path, file_data)
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
    file_types, file_data = get_file_types(repo.path)
    structure = get_directory_structure(repo.path, file_data)
    dir_structure = render_directory_structure(structure)
    
    checkboxes = [
        Checkbox(name="file_types", value=ext, label=f"{ext} ({info['count']} files, {info['size']} bytes, {info['tokens']} tokens)")
        for ext, info in file_types.items()
    ]
    
    return Titled(f"Repository: {repo.name}",
        Form(
            H3("File Type Exclusions"),
            Div(*checkboxes, id="file-types", hx_post="/update-totals", hx_trigger="change", hx_target="#totals"),
            P("Total: 0 files, 0 bytes, 0 tokens", id="totals"),
            H3("Directory Structure"),
            Div(
                Button("Select All", hx_post="/select-all", hx_target="#directory-structure"),
                Button("Unselect All", hx_post="/unselect-all", hx_target="#directory-structure")
            ),
            Div(dir_structure, id="directory-structure", hx_trigger="change", hx_post="/update-totals", hx_target="#totals"),
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