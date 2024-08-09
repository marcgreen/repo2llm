import pytest
from starlette.testclient import TestClient
from app import app

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

def test_clone_route(client, mocker):
    mocker.patch('subprocess.run')
    mocker.patch('os.path.exists', return_value=False)
    response = client.post('/clone', data={'url': 'https://github.com/user/repo.git'})
    assert response.status_code == 200
    assert app.state.current_repo is not None
    assert app.state.current_repo.name == 'repo'

def test_update_totals_route(client, mock_repo_structure, mock_current_repo):
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