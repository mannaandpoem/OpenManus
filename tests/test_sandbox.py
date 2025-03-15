"""Tests for the sandbox functionality in the OpenManus system."""
import asyncio
import os
import shutil
from pathlib import Path
import pytest

from app.tool.python_execute import PythonExecute
from app.tool.file_saver import FileSaver
from app.tool.terminal import Terminal
from app.tool.sandbox_utils import SandboxUtils


# Setup and teardown functions
@pytest.fixture
def sandbox_dir():
    """Create and return the sandbox directory path."""
    sandbox = SandboxUtils()
    return sandbox.sandbox_dir


@pytest.fixture(autouse=True)
def clean_sandbox_before_test(sandbox_dir):
    """Clean the sandbox directory before each test."""
    # Make sure sandbox exists
    if not sandbox_dir.exists():
        sandbox_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean it
    for item in sandbox_dir.glob("*"):
        if item.is_file():
            item.unlink()
        elif item.is_dir() and item.name != ".git":
            shutil.rmtree(item)
    
    yield  # Run the test
    
    # Clean up after the test too
    for item in sandbox_dir.glob("*"):
        if item.is_file() and item.name != "README.md":
            item.unlink()
        elif item.is_dir() and item.name != ".git":
            shutil.rmtree(item)


# Tests for PythonExecute
@pytest.mark.asyncio
async def test_python_execute_sandbox_containment(sandbox_dir):
    """Test that Python execution is contained within the sandbox directory."""
    tool = PythonExecute()
    
    # Test file creation inside sandbox
    code = """
with open('test_file.txt', 'w') as f:
    f.write('test content')
print('File created')
"""
    result = await tool.execute(code)
    print(f"\nExecution result: {result}")  # Debug output
    assert result["success"], f"Execution failed: {result['observation']}"
    assert "File created" in result["observation"]
    
    # Verify file was created in sandbox
    assert (sandbox_dir / "test_file.txt").exists()
    assert (sandbox_dir / "test_file.txt").read_text() == "test content"
    
    # Test that access outside sandbox is prevented
    code = """
with open('../outside_sandbox.txt', 'w') as f:
    f.write('should not work')
"""
    result = await tool.execute(code)
    assert not result["success"]
    assert "potentially harmful" in result["observation"]
    
    # Verify no file was created outside sandbox
    assert not Path("outside_sandbox.txt").exists()


@pytest.mark.asyncio
async def test_python_execute_with_permissions(sandbox_dir):
    """Test that Python execution can access outside resources with permission."""
    tool = PythonExecute()
    
    # Create a temporary file to access
    temp_file = Path(os.getcwd()) / "temp_test_file.txt"
    temp_file.write_text("external content")
    
    try:
        # Try to read the file with permission
        code = """
with open('../temp_test_file.txt', 'r') as f:
    content = f.read()
print(f'Read content: {content}')
"""
        result = await tool.execute(code, allow_external_access=True)
        assert result["success"]
        assert "Read content: external content" in result["observation"]
    finally:
        # Clean up the temporary file
        if temp_file.exists():
            temp_file.unlink()


# Tests for FileSaver
@pytest.mark.asyncio
async def test_file_saver_sandbox_containment(sandbox_dir):
    """Test that FileSaver correctly restricts file operations to the sandbox."""
    tool = FileSaver()
    
    # Test saving in sandbox
    result = await tool.execute("Test content", "test_saved.txt")
    assert result["success"]
    
    # Verify file was saved in sandbox
    assert (sandbox_dir / "test_saved.txt").exists()
    assert (sandbox_dir / "test_saved.txt").read_text() == "Test content"
    
    # Test saving outside sandbox is prevented
    result = await tool.execute("Should be prevented", "/tmp/external_file.txt")
    assert not result["success"]
    assert "without explicit permission" in result["observation"]
    
    # Verify no file was created in the requested location
    assert not Path("/tmp/external_file.txt").exists()


@pytest.mark.asyncio
async def test_file_saver_with_permissions(sandbox_dir):
    """Test that FileSaver can save outside sandbox with permission."""
    tool = FileSaver()
    
    # Create a temporary location for testing
    temp_dir = Path(os.getcwd()) / "temp_test_dir"
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # Try to save with permission
        test_file = temp_dir / "external_save.txt"
        result = await tool.execute(
            "External content", 
            str(test_file), 
            allow_external_access=True
        )
        assert result["success"]
        
        # Verify file was saved in requested location
        assert test_file.exists()
        assert test_file.read_text() == "External content"
    finally:
        # Clean up
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


# Tests for Terminal
@pytest.mark.asyncio
async def test_terminal_sandbox_containment(sandbox_dir):
    """Test that Terminal execution is contained within the sandbox directory."""
    tool = Terminal()
    
    # Test command execution in sandbox
    result = await tool.execute("touch test_terminal.txt && ls")
    assert "test_terminal.txt" in result.output
    
    # Verify file was created in sandbox
    assert (sandbox_dir / "test_terminal.txt").exists()
    
    # Test that harmful commands are blocked
    result = await tool.execute("rm -rf /")
    assert "potentially harmful" in result.error
    
    # Test that access outside sandbox is constrained
    result = await tool.execute("cd .. && pwd")
    # Should still be in sandbox after attempted escape
    assert str(sandbox_dir) in result.output


@pytest.mark.asyncio
async def test_terminal_with_permissions(sandbox_dir):
    """Test that Terminal can access outside resources with permission."""
    tool = Terminal()
    
    # Create a temporary directory for testing
    temp_dir = Path(os.getcwd()) / "temp_cmd_dir"
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # Execute command with permission
        result = await tool.execute(
            f"cd {temp_dir} && touch external_cmd.txt && ls",
            allow_external_access=True
        )
        assert "external_cmd.txt" in result.output
        
        # Verify file was created in requested location
        assert (temp_dir / "external_cmd.txt").exists()
    finally:
        # Clean up
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


# Integration Tests
@pytest.mark.asyncio
async def test_sandbox_isolation_integration(sandbox_dir):
    """Test that sandbox isolation works across all tools."""
    python_tool = PythonExecute()
    file_tool = FileSaver()
    terminal_tool = Terminal()
    
    # Create a file with Python
    python_result = await python_tool.execute("""
with open('integration_test.txt', 'w') as f:
    f.write('Integration test content')
print('File created')
""")
    assert python_result["success"]
    
    # Verify file exists and read it with FileSaver
    assert (sandbox_dir / "integration_test.txt").exists()
    
    # List the file with Terminal
    terminal_result = await terminal_tool.execute("ls")
    assert "integration_test.txt" in terminal_result.output
    
    # Try to access it from outside sandbox - should fail
    python_result = await python_tool.execute("""
import os
print(os.path.abspath('integration_test.txt'))
""")
    assert python_result["success"]
    assert str(sandbox_dir) in python_result["observation"]


@pytest.mark.asyncio
async def test_sandbox_permission_boundaries(sandbox_dir):
    """Test that permission boundaries are correctly enforced across tools."""
    python_tool = PythonExecute()
    file_tool = FileSaver()
    
    # Try to access a file outside sandbox with Python
    outside_path = "../outside_sandbox_file.txt"
    
    # 1. Without permission - should fail
    python_result = await python_tool.execute(f"""
try:
    with open('{outside_path}', 'w') as f:
        f.write('Should not work')
    print('File written')
except Exception as e:
    print(f'Error: {{e}}')
""")
    assert not python_result["success"]
    assert "potentially harmful" in python_result["observation"]
    
    # Verify no file was created
    assert not Path("outside_sandbox_file.txt").exists()
    
    # 2. With permission - should work
    python_result = await python_tool.execute(f"""
with open('{outside_path}', 'w') as f:
    f.write('Should work with permission')
print('File written with permission')
""", allow_external_access=True)
    assert python_result["success"]
    assert "File written with permission" in python_result["observation"]
    
    # Verify file was created
    outside_file = Path(os.getcwd()) / "outside_sandbox_file.txt"
    try:
        assert outside_file.exists()
        assert outside_file.read_text() == "Should work with permission"
    finally:
        # Clean up
        if outside_file.exists():
            outside_file.unlink() 