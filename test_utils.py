import pytest
import os
import tempfile
from utils import count_tokens, get_file_types, get_directory_structure


def test_count_tokens():
    assert count_tokens("Hello, world!") == 4
    assert count_tokens("") == 0
    assert count_tokens("a" * 1000) > 100


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create a mock repository structure
        os.makedirs(os.path.join(tmpdirname, "dir1"))
        os.makedirs(os.path.join(tmpdirname, "dir2"))

        with open(os.path.join(tmpdirname, "file1.txt"), "w") as f:
            f.write("Hello, world!")
        with open(os.path.join(tmpdirname, "file2.py"), "w") as f:
            f.write("print('Hello, world!')")
        with open(os.path.join(tmpdirname, "dir1", "file3.js"), "w") as f:
            f.write("console.log('Hello, world!');")

        yield tmpdirname


def test_get_file_types(temp_repo):
    file_types, file_data = get_file_types(temp_repo)

    assert set(file_types.keys()) == {".txt", ".py", ".js"}
    assert all(key in file_types[".txt"]
               for key in ["count", "size", "tokens"])
    assert file_types[".txt"]["count"] == 1
    assert file_types[".py"]["count"] == 1
    assert file_types[".js"]["count"] == 1

    assert len(file_data) == 3
    assert all(
        os.path.basename(path) in ["file1.txt", "file2.py", "file3.js"]
        for path in file_data.keys())



def test_get_directory_structure(temp_repo):
    _, file_data = get_file_types(temp_repo)
    data = get_directory_structure(temp_repo, file_data)
    print(data)
    
    # Check for the presence of file information
    assert 'file1.txt' in data
    assert 'file2.py' in data
    assert 'dir1/file3.js' in data
    # assert '100 bytes, 50 tokens' in data
    # assert '200 bytes, 100 tokens' in data
    # assert '150 bytes, 75 tokens' in data