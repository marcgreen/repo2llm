import pytest
from app import app
import os
import json

from bs4 import BeautifulSoup


from utils import get_directory_structure


@pytest.fixture
def mock_repo_structure(mocker):
    mock_file_types = {
        '.py': {
            'count': 1,
            'size': 100,
            'tokens': 50
        },
        '.txt': {
            'count': 1,
            'size': 200,
            'tokens': 100
        },
        '.js': {
            'count': 1,
            'size': 150,
            'tokens': 75
        }
    }
    mock_file_data = {
        'file1.py': {
            'count': 1,
            'size': 100,
            'tokens': 50
        },
        'file2.txt': {
            'count': 1,
            'size': 200,
            'tokens': 100
        },
        'subdir/file3.js': {
            'count': 1,
            'size': 150,
            'tokens': 75
        }
    }

    def mock_get_file_types(repo_path):
        return mock_file_types, mock_file_data

    mocker.patch('app.get_file_types', side_effect=mock_get_file_types)
    # Use the actual get_directory_structure function
    mocker.patch('app.get_directory_structure', side_effect=get_directory_structure)


@pytest.fixture
def client(mock_repo_structure):
    app.config['TESTING'] = True
    app.config['SUBDIRECTORY'] = 'test_repos'
    app.config['REPO_NAME'] = 'test_repo'
    with app.test_client() as client:
        yield client


def test_update_totals_route(client):
    response = client.post('/update-totals',
                           data={
                               'selected_files':
                               ['file1.py', 'subdir/file3.js'],
                               'file_types': ['.txt']
                           })
    assert response.status_code == 200
    assert b'Total: 2 files, 250 bytes, 125 tokens' in response.data


def test_select_all_route(client):
    response = client.post('/select-all')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert '<input type="checkbox" checked' in data['html']
    assert 'file1.py' in data['html']
    assert 'file2.txt' in data['html']
    assert 'subdir/file3.js' in data['html']


def test_unselect_all_route(client):
    response = client.post('/unselect-all')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert '<input type="checkbox"' in data['html']
    assert 'checked' not in data['html']
    assert 'file1.py' in data['html']
    assert 'file2.txt' in data['html']
    assert 'subdir/file3.js' in data['html']

def test_home_route(client):
    app.config['REPO_NAME'] = ''  # Ensure no repo is set
    response = client.get('/')
    assert response.status_code == 200
    assert b'GitHub URL:' in response.data


def test_clone_route(client, mocker):
    mocker.patch('subprocess.run')
    mocker.patch('os.path.exists', return_value=False)
    mocker.patch('utils.get_file_types', return_value=({'.py': {'count': 1, 'size': 100, 'tokens': 50}}, {}))
    mocker.patch('utils.get_directory_structure', return_value='<ul><li>file.py</li></ul>')

    response = client.post('/clone', data={'url': 'https://github.com/user/repo.git'})
    assert response.status_code == 200
    assert b'File Type Exclusions' in response.data
    assert b'<form hx-post="/combine" hx-target="#content">' in response.data
    assert b'.py (1 files, 100 bytes, 50 tokens)' in response.data


def test_combine_route(client, mocker):
    mocker.patch('builtins.open', mocker.mock_open(read_data="file content"))

    response = client.post('/combine', data={'selected_files': ['file1.py']})
    assert response.status_code == 200
    assert b'>>> FILE: file1.py <<<' in response.data
    assert b'file content' in response.data


def test_delete_route(client, mocker):
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('subprocess.run')

    response = client.post('/delete')
    assert response.status_code == 200
    assert b'GitHub URL:' in response.data

def test_update_totals_with_file_selection(client):
    response = client.post('/update-totals',
                           data={
                               'selected_files': ['file1.py'],
                               'file_types': []
                           })
    assert response.status_code == 200
    assert b'Total: 1 files, 100 bytes, 50 tokens' in response.data

def test_unselect_all_preserves_structure(client, mocker):
    mock_file_data = {
        'file1.py': {'size': 100, 'tokens': 50},
        'subdir/file2.js': {'size': 150, 'tokens': 75}
    }
    mocker.patch('app.get_file_types', return_value=({}, mock_file_data))
    response = client.post('/unselect-all')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert '<input type="checkbox"' in data['html']
    assert 'checked' not in data['html']
    assert '<li class="directory">' in data['html']
    assert '<ul style="display: none;">' in data['html']

def test_directory_structure_collapsible(client, mocker):
    mock_file_data = {
        'file1.py': {'size': 100, 'tokens': 50},
        'subdir/file2.js': {'size': 150, 'tokens': 75}
    }
    mocker.patch('app.get_file_types', return_value=({}, mock_file_data))
    app.config['REPO_NAME'] = 'test_repo'  # Ensure a repo is set
    response = client.get('/')
    assert response.status_code == 200
    assert b'<li class="directory">' in response.data
    assert b'<span class="toggle">+</span>' in response.data
    assert b'<ul style="display: none;">' in response.data