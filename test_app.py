import pytest
from starlette.testclient import TestClient
from fasthtml.common import Li, Checkbox, Button, Ul
from app import app, SUBDIRECTORY, Repo, get_current_repo
import os
import threading
import time
import requests
from requests.exceptions import RequestException
from playwright.sync_api import Page, expect
from fasthtml.common import serve
import subprocess
import signal

playwright_tests = pytest.mark.playwright

PORT = 5001


@pytest.fixture(scope="session", autouse=True)
def server(request):
    print("Starting server...")
    process = subprocess.Popen(
        ["poetry", "run", "python", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def print_output():
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())

    import threading
    thread = threading.Thread(target=print_output)
    thread.start()

    # Wait for the server to start
    for _ in range(30):  # Try for 30 seconds
        try:
            response = requests.get(f"http://localhost:{PORT}")
            if response.status_code == 200:
                print("Server started successfully")
                break
        except RequestException:
            time.sleep(1)
    else:
        print("Server did not start within 30 seconds.")
        process.send_signal(signal.SIGINT)
        process.wait()
        pytest.fail("Server did not start within 30 seconds")

    def fin():
        print("Stopping server...")
        process.send_signal(signal.SIGINT)
        process.wait()
        thread.join()
        print("Server stopped.")

    request.addfinalizer(fin)

    return process

@pytest.fixture(scope="module")
def page(playwright):
    browser = playwright.chromium.launch()
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()
    browser.close()

@pytest.fixture
def mock_repo(tmp_path):
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    (repo_path / "file1.py").write_text("print('Hello')")
    (repo_path / "file2.txt").write_text("Hello, world!")
    subdir = repo_path / "subdir"
    subdir.mkdir()
    (subdir / "file3.js").write_text("console.log('Hello');")
    return Repo(name="test_repo", path=os.path.join(SUBDIRECTORY, "test_repo"))

@pytest.fixture
def loaded_repo_page(page, mock_repo):
    app.state.current_repo = None  # Reset the current repo
    page.goto("http://localhost:5001")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="debug_screenshot1.png")
    page.fill("input[name='url']", f"file://{mock_repo}")
    page.click("button:has-text('Clone Repository')")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="debug_screenshot2.png")
    page.wait_for_selector("text=File Type Exclusions")
    return page


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

@playwright_tests
def test_directory_structure_toggle(loaded_repo_page):
    page = loaded_repo_page
    
    toggles = page.locator(".toggle")
    
    for i in range(toggles.count()):
        toggle = toggles.nth(i)
        parent = toggle.locator("xpath=..")
        children = parent.locator("xpath=./ul/li")
        
        if children.count() > 0:
            expect(children).to_have_css("display", "none")
            
            toggle.click()
            expect(children).not_to_have_css("display", "none")
            
            toggle.click()
            expect(children).to_have_css("display", "none")
    
    if toggles.count() > 1:
        parent_toggle = toggles.first
        parent_toggle.click()
        
        child_toggle = parent_toggle.locator("xpath=../ul/li").locator(".toggle").first
        if child_toggle.count() > 0:
            child_toggle.click()
            grandchild = child_toggle.locator("xpath=../ul/li").first
            
            expect(grandchild).not_to_have_css("display", "none")
            
            parent_toggle.click()
            parent_toggle.click()
            expect(grandchild).to_have_css("display", "none")

@playwright_tests
def test_select_all_visual_update(loaded_repo_page):
    page = loaded_repo_page
    
    checkboxes = page.locator("input[name='selected_files']")
    total_checkboxes = checkboxes.count()
    
    if total_checkboxes == 0:
        pytest.skip("No files to select")
    
    initial_checked_count = checkboxes.evaluate_all("nodes => nodes.filter(n => n.checked).length")
    
    page.click("button:has-text('Select All')")
    expect(checkboxes).to_have_count(total_checkboxes)
    for checkbox in checkboxes.all():
        expect(checkbox).to_be_checked()
    
    expect(page.locator("#totals")).not_to_have_text("Total: 0 files")
    
    page.click("button:has-text('Unselect All')")
    for checkbox in checkboxes.all():
        expect(checkbox).not_to_be_checked()
    
    expect(page.locator("#totals")).to_have_text("Total: 0 files, 0 bytes, 0 tokens")
    
    if total_checkboxes > 1:
        page.click("button:has-text('Select All')")
        checkboxes.first.uncheck()
        expect(checkboxes.first).not_to_be_checked()
        expect(checkboxes.nth(1)).to_be_checked()
        
        new_total = page.locator("#totals").inner_text()
        assert new_total != "Total: 0 files, 0 bytes, 0 tokens"
        assert new_total != f"Total: {total_checkboxes} files"

@playwright_tests
def test_file_type_exclusion_visual_feedback(loaded_repo_page):
    page = loaded_repo_page
    
    page.click("button:has-text('Select All')")
    
    file_type_checkboxes = page.locator("input[name='file_types']")
    
    for i in range(file_type_checkboxes.count()):
        file_type_checkbox = file_type_checkboxes.nth(i)
        file_type = file_type_checkbox.get_attribute("value")
        
        file_type_checkbox.check()
        
        excluded_files = page.locator(f"input[name='selected_files'][disabled]")
        for file in excluded_files.all():
            expect(file).to_be_disabled()
            expect(file.locator("..")).to_have_css("opacity", "0.5")
        
        included_files = page.locator(f"input[name='selected_files']:not([disabled])")
        for file in included_files.all():
            expect(file).to_be_enabled()
            expect(file.locator("..")).not_to_have_css("opacity", "0.5")
        
        total_files = page.locator("input[name='selected_files']").count()
        current_total = int(page.locator("#totals").inner_text().split()[1])
        assert current_total <= total_files
        
        file_type_checkbox.uncheck()
        expect(page.locator(f"input[name='selected_files'][disabled]")).to_have_count(0)
    
    if file_type_checkboxes.count() >= 2:
        file_type_checkboxes.first.check()
        file_type_checkboxes.nth(1).check()
        
        excluded_count = page.locator("input[name='selected_files'][disabled]").count()
        total_count = page.locator("input[name='selected_files']").count()
        
        assert excluded_count > 0 and excluded_count < total_count
        
        total_text = page.locator("#totals").inner_text()
        assert int(total_text.split()[1]) == total_count - excluded_count
    
    for checkbox in file_type_checkboxes.all():
        checkbox.check()
    
    select_all_button = page.locator("button:has-text('Select All')")
    expect(select_all_button).to_be_disabled()