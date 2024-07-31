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
    assert all(key in file_types[".txt"] for key in ["count", "size", "tokens"])
    assert file_types[".txt"]["count"] == 1
    assert file_types[".py"]["count"] == 1
    assert file_types[".js"]["count"] == 1

    assert len(file_data) == 3
    assert all(os.path.basename(path) in ["file1.txt", "file2.py", "file3.js"] for path in file_data.keys())

def test_get_directory_structure(temp_repo):
    _, file_data = get_file_types(temp_repo)
    structure = get_directory_structure(temp_repo, file_data)
    
    # Check if the structure is a dictionary
    assert isinstance(structure, dict)
    
    # Check the root structure
    assert structure['name'] == os.path.basename(temp_repo)
    assert structure['type'] == 'directory'
    assert 'children' in structure
    
    # Check the children
    children = structure['children']
    assert len(children) == 4  # file1.txt, file2.py, dir1, and dir2
    
    # Check for specific files/directories
    file_names = [child['name'] for child in children]
    assert 'file1.txt' in file_names
    assert 'file2.py' in file_names
    assert 'dir1' in file_names
    assert 'dir2' in file_names
    
    # Check a file's details
    file1 = next(child for child in children if child['name'] == 'file1.txt')
    assert file1['type'] == 'file'
    assert file1['size'] == 13
    assert file1['tokens'] == 4
    
    # Check the nested directory
    dir1 = next(child for child in children if child['name'] == 'dir1')
    assert dir1['type'] == 'directory'
    assert len(dir1['children']) == 1
    
    # Check the file in the nested directory
    file3 = dir1['children'][0]
    assert file3['name'] == 'file3.js'
    assert file3['type'] == 'file'
    assert file3['size'] == 29
    assert file3['tokens'] == 8
    
    # Check the empty directory
    dir2 = next(child for child in children if child['name'] == 'dir2')
    assert dir2['type'] == 'directory'
    assert len(dir2['children']) == 0