"""Tests for the AskUser functionality in the OpenManus system."""
import pytest

from app.tool.ask_user import AskUser


@pytest.mark.asyncio
async def test_ask_user_basic_functionality():
    """Test that AskUser tool correctly formats questions and requires user response."""
    tool = AskUser()
    
    # Test basic question
    result = await tool.execute("Do you want to proceed with this action?")
    assert result["success"]
    assert "CONFIRMATION: Do you want to proceed with this action?" in result["observation"]
    assert result["requires_user_response"]
    
    # Test with dangerous action flag
    result = await tool.execute(
        "Do you want to delete all files in the sandbox?", 
        dangerous_action=True
    )
    assert result["success"]
    assert "CAUTION: Do you want to delete all files in the sandbox?" in result["observation"]
    assert result["requires_user_response"]
    
    # Test with longer question text
    long_question = (
        "This action will delete all files in your project directory. "
        "This operation cannot be undone. Are you absolutely sure you want to proceed?"
    )
    result = await tool.execute(long_question, dangerous_action=True)
    assert result["success"]
    assert f"CAUTION: {long_question}" in result["observation"]
    assert result["requires_user_response"] 