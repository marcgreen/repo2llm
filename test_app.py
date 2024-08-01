import pytest
from starlette.testclient import TestClient
from fasthtml.common import Li, Checkbox, Button, Ul
from app import app, SUBDIRECTORY, Repo, get_current_repo
import os

@pytest.fixture
def mock_repo_structure(mocker):
    mock_file_types = {
        '.py': {'count': 1, 'size': 100, 'tokens': 50},
        '.txt': {'count': 1, 'size': 200, 'tokens': 100},
        '.js': {'count': 1, 'size': 150, 'tokens': 75},
        '.gitignore': {'count': 1, 'size': 20, 'tokens': 10},
        '(no extension)': {'count': 1, 'size': 50, 'tokens': 25}
    }
    mock_file_data = {
        'file1.py': {'count': 1, 'size': 100, 'tokens': 50},
        'file2.txt': {'count': 1, 'size': 200, 'tokens': 100},
        'subdir/file3.js': {'count': 1, 'size': 150, 'tokens': 75},
        '.gitignore': {'count': 1, 'size': 20, 'tokens': 10},
        'LICENSE': {'count': 1, 'size': 50, 'tokens': 25}
    }
    mock_skipped_files = ['binary_file']

    def mock_get_file_types(repo_path):
        return mock_file_types, mock_file_data, mock_skipped_files

    mocker.patch('app.get_file_types', side_effect=mock_get_file_types)
    mocker.patch('app.get_directory_structure', return_value={
        'type': 'directory',
        'name': 'test_repo',
        'path': '/path/to/test_repo',
        'children': [
            {
                'type': 'file',
                'name': 'file1.py',
                'path': '/path/to/test_repo/file1.py',
                'size': 100,
                'tokens': 50
            },
            {
                'type': 'file',
                'name': 'file2.txt',
                'path': '/path/to/test_repo/file2.txt',
                'size': 200,
                'tokens': 100
            },
            {
                'type': 'directory',
                'name': 'subdir',
                'path': '/path/to/test_repo/subdir',
                'children': [
                    {
                        'type': 'file',
                        'name': 'file3.js',
                        'path': '/path/to/test_repo/subdir/file3.js',
                        'size': 150,
                        'tokens': 75
                    }
                ]
            },
            {
                'type': 'file',
                'name': '.gitignore',
                'path': '/path/to/test_repo/.gitignore',
                'size': 20,
                'tokens': 10
            },
            {
                'type': 'file',
                'name': 'LICENSE',
                'path': '/path/to/test_repo/LICENSE',
                'size': 50,
                'tokens': 25
            },
            {
                'type': 'file',
                'name': 'binary_file',
                'path': '/path/to/test_repo/binary_file',
                'skipped': True
            }
        ]
    })

@pytest.fixture
def mock_repo():
    return Repo(name="test_repo", path=os.path.join(SUBDIRECTORY, "test_repo"))

@pytest.fixture
def mock_current_repo(mocker, mock_repo):
    def mock_get_current_repo(request):
        return mock_repo
    mocker.patch('app.get_current_repo', side_effect=mock_get_current_repo)
    return mock_repo

@pytest.fixture
def client(mock_repo_structure, mock_current_repo):
    with TestClient(app, follow_redirects=True) as client:
        app.state.current_repo = mock_current_repo
        yield client

def test_home_route_no_repo(client, mocker):
    mocker.patch('app.get_current_repo', return_value=None)
    response = client.get('/')
    assert response.status_code == 200
    assert 'GitHub URL:' in response.text

def test_home_route_with_repo(client, mock_current_repo):
    response = client.get('/')
    assert response.status_code == 200
    assert 'File Type Exclusions' in response.text
    assert 'Total: 5 files, 520 bytes, 260 tokens' in response.text

def test_initial_totals_calculation(client, mock_current_repo):
    response = client.get('/')
    assert response.status_code == 200
    assert 'Total: 5 files, 520 bytes, 260 tokens' in response.text
    
def test_clone_route(client, mocker):
    mocker.patch('subprocess.run')
    mocker.patch('os.path.exists', return_value=False)
    response = client.post('/clone', data={'url': 'https://github.com/user/repo.git'})
    assert response.status_code == 200
    assert app.state.current_repo is not None
    assert app.state.current_repo.name == 'repo'

def test_update_totals_route(client, mock_current_repo):
    response = client.post('/update-totals', data={'selected_files': ['file1.py', 'subdir/file3.js'], 'file_types': ['.txt']})
    assert response.status_code == 200
    assert 'Total: 2 files, 250 bytes, 125 tokens' in response.text

def test_combine_route(client, mock_current_repo, mocker):
    mocker.patch('builtins.open', mocker.mock_open(read_data="file content"))
    mocker.patch('os.path.exists', return_value=True)
    response = client.post('/combine', data={'selected_files': ['file1.py'], 'file_types': []})
    assert response.status_code == 200
    assert '&gt;&gt;&gt; FILE: file1.py &lt;&lt;&lt;' in response.text
    assert 'file content' in response.text

def test_select_all_route(client, mock_current_repo):
    response = client.post('/select-all')
    assert response.status_code == 200
    assert 'checked' in response.text
    assert 'file1.py' in response.text
    assert 'file2.txt' in response.text
    assert 'file3.js' in response.text

def test_unselect_all_route(client, mock_current_repo):
    response = client.post('/unselect-all')
    assert response.status_code == 200
    assert 'checked' not in response.text

def test_delete_route(client, mock_current_repo, mocker):
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('subprocess.run')
    response = client.post('/delete')
    assert response.status_code == 200
    assert app.state.current_repo is None

def test_dotfile_in_directory_structure(client, mock_current_repo):
    response = client.get('/')
    assert response.status_code == 200
    assert '.gitignore' in response.text

def test_no_extension_file_in_directory_structure(client, mock_current_repo):
    response = client.get('/')
    assert response.status_code == 200
    assert 'LICENSE' in response.text

def test_skipped_file_in_directory_structure(client, mock_current_repo):
    response = client.get('/')
    assert response.status_code == 200
    assert 'binary_file' in response.text
    assert 'Binary or unreadable file - skipped' in response.text

def test_update_totals_with_dotfile(client, mock_current_repo):
    response = client.post('/update-totals', data={'selected_files': ['.gitignore'], 'file_types': []})
    assert response.status_code == 200
    assert 'Total: 1 files, 20 bytes, 10 tokens' in response.text

def test_update_totals_with_no_extension_file(client, mock_current_repo):
    response = client.post('/update-totals', data={'selected_files': ['LICENSE'], 'file_types': []})
    assert response.status_code == 200
    assert 'Total: 1 files, 50 bytes, 25 tokens' in response.text

def test_directory_structure_collapsible(client, mock_current_repo):
    response = client.get('/')
    assert response.status_code == 200
    assert 'class="toggle"' in response.text
    assert 'style="display: none;"' in response.text

def test_get_current_repo(client, mock_current_repo):
    response = client.get('/')
    assert response.status_code == 200
    assert 'Repository: test_repo' in response.text