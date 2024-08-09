import pytest
import subprocess
import signal
import time
import requests
from requests.exceptions import RequestException
from app import app, SUBDIRECTORY, Repo
import os
from starlette.testclient import TestClient
import pytest
import os
import shutil
import subprocess
from pathlib import Path

PORT = 5001

@pytest.fixture(scope="session", autouse=True)
def server(request):
    process = None
    try:
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

        yield process
    finally:
        if process:
            print("Stopping server...")
            process.send_signal(signal.SIGINT)
            process.wait()
            print("Server stopped.")

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

# for nonui tests
@pytest.fixture
def loaded_repo_page(page, mock_repo):
    app.state.current_repo = None  # Reset the current repo
    page.goto(f"http://localhost:{PORT}")
    page.wait_for_load_state("networkidle")
    page.fill("input[name='url']", f"file://{mock_repo.path}")
    page.click("button:has-text('Clone Repository')")
    page.wait_for_load_state("networkidle")
    # take screenshot
    page.screenshot(path="test_ui.png")
    page.wait_for_selector("text=File Type Exclusions")
    return page

@pytest.fixture(autouse=True)
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
        print("mock_get_file_types called")
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

@pytest.fixture(scope="session")
def test_git_repo():
    # Define the path for our test repository
    repo_path = Path(__file__).parent / "test_repos" / "test_repo"
    
    # Create the directory if it doesn't exist
    repo_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize git repository if it doesn't exist
    if not (repo_path / ".git").exists():
        subprocess.run(["git", "init"], cwd=repo_path)
        
        # Create a simple directory structure with various file types
        (repo_path / "file1.py").write_text("print('Hello from Python')")
        (repo_path / "file2.js").write_text("console.log('Hello from JavaScript');")
        (repo_path / "file3.txt").write_text("Hello from a text file")
        (repo_path / "file4.md").write_text("# Hello from Markdown")
        
        subdir = repo_path / "subdir"
        subdir.mkdir(exist_ok=True)
        (subdir / "file5.py").write_text("print('Hello from subdirectory')")
        (subdir / "file6.cpp").write_text("cout << 'Hello from C++' << endl;")
        
        # Add and commit the files
        subprocess.run(["git", "add", "."], cwd=repo_path)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path)
    
    yield repo_path
    
    # No cleanup needed as we're keeping the repo for future test runs

@pytest.fixture
def loaded_ui_test_repo_page(page, test_git_repo):
    app.state.current_repo = None  # Reset the current repo
    page.goto(f"http://localhost:{PORT}")
    page.wait_for_load_state("networkidle")
    page.fill("input[name='url']", f"file://{test_git_repo}")
    page.click("button:has-text('Clone Repository')")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("text=File Type Exclusions")
    return page