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
        with open(os.path.join(tmpdirname, ".gitignore"), "w") as f:
            f.write("*.log\n*.tmp")
        with open(os.path.join(tmpdirname, "LICENSE"), "w") as f:
            f.write("MIT License")
        with open(os.path.join(tmpdirname, "binary_file"), "wb") as f:
            f.write(b'\x00\x01\x02\x03')

        yield tmpdirname


def test_get_file_types(temp_repo):
    file_types, file_data, skipped_files = get_file_types(temp_repo)

    assert set(file_types.keys()) == {".txt", ".py", ".js", ".gitignore", "(no extension)"}
    assert all(key in file_types[".txt"] for key in ["count", "size", "tokens"])
    assert file_types[".txt"]["count"] == 1
    assert file_types[".py"]["count"] == 1
    assert file_types[".js"]["count"] == 1
    assert file_types[".gitignore"]["count"] == 1
    assert file_types["(no extension)"]["count"] == 1  # Only LICENSE, binary_file should be skipped

    assert len(file_data) == 5  # 5 readable files
    assert len(skipped_files) == 1  # binary_file should be skipped

def test_get_directory_structure(temp_repo):
    _, file_data, skipped_files = get_file_types(temp_repo)
    structure = get_directory_structure(temp_repo, file_data, skipped_files)
    
    assert isinstance(structure, dict)
    assert structure['name'] == os.path.basename(temp_repo)
    assert structure['type'] == 'directory'
    assert 'children' in structure
    
    children = structure['children']
    assert len(children) == 6  # file1.txt, file2.py, dir1, dir2, .gitignore, LICENSE
    
    file_names = [child['name'] for child in children]
    assert 'file1.txt' in file_names
    assert 'file2.py' in file_names
    assert '.gitignore' in file_names
    assert 'LICENSE' in file_names
    assert 'dir1' in file_names
    assert 'dir2' in file_names

    binary_file = next(child for child in children if child['name'] == 'binary_file')
    assert binary_file['skipped'] == True
    
    file1 = next(child for child in children if child['name'] == 'file1.txt')
    assert file1['type'] == 'file'
    assert file1['size'] == 13
    assert file1['tokens'] == 4
    
    dir1 = next(child for child in children if child['name'] == 'dir1')
    assert dir1['type'] == 'directory'
    assert len(dir1['children']) == 1
    
    file3 = dir1['children'][0]
    assert file3['name'] == 'file3.js'
    assert file3['type'] == 'file'
    assert file3['size'] == 29
    assert file3['tokens'] == 8
    
    dir2 = next(child for child in children if child['name'] == 'dir2')
    assert dir2['type'] == 'directory'
    assert len(dir2['children']) == 0

def test_dotfile_handling(temp_repo):
    file_types, _, _ = get_file_types(temp_repo)
    assert '.gitignore' in file_types
    assert file_types['.gitignore']['count'] == 1

def test_no_extension_handling(temp_repo):
    file_types, _, _ = get_file_types(temp_repo)
    assert '(no extension)' in file_types
    assert file_types['(no extension)']['count'] == 2  # LICENSE and binary_file



def test_binary_file_skipping(temp_repo):
    _, _, skipped_files = get_file_types(temp_repo)
    assert len(skipped_files) == 1
    assert 'binary_file' in skipped_files[0]