import pytest
from app import app

def test_initial_totals_calculation(client, mock_current_repo):
    response = client.get('/')
    assert response.status_code == 200
    assert 'Total: 5 files, 520 bytes, 260 tokens' in response.text

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