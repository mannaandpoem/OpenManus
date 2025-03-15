import json
from app.schema import Function, ToolCall
from app.logger import logger

def create_ask_user_tool_call(question_text: str):
    """
    Safely create an ask_user tool call from a question text.
    """
    try:
        # Trim question text if too long to prevent JSON serialization issues
        max_length = 500
        if len(question_text) > max_length:
            question_text = question_text[:max_length] + "..."
            
        # Sanitize question text for JSON 
        # Replace newlines with spaces and escape quotes for JSON safety
        question_text = question_text.replace('\n', ' ').replace('\r', ' ')
        
        # Create the arguments as a proper Python dictionary first
        args = {
            "question": question_text,
            "dangerous_action": False,
            "question_type": "follow-up"
        }
        
        # Convert to JSON with error handling
        args_json = json.dumps(args)
        
        # Create the function object using the schema's Function class
        function_obj = Function(
            name="ask_user",
            arguments=args_json
        )
        
        # Create the full tool call
        ask_user_tool = ToolCall(
            id="auto_ask_user",
            type="function",
            function=function_obj
        )
        
        print(f"Successfully created tool call: {ask_user_tool}")
        return [ask_user_tool]
            
    except Exception as e:
        print(f"Error creating ask_user tool call: {str(e)}, {type(e)}")
        return []

# Test with different inputs
test_inputs = [
    "Simple question?",
    "Multiple line\nquestion with\nline breaks",
    "Very long " + "question " * 100,
    """Complex formatting with:
    - Bullet points
    - Numbered lists
    - Indentation
    
    And special characters: " ' \ / """,
]

for i, test_input in enumerate(test_inputs):
    print(f"\nTest {i+1}: {test_input[:50]}...")
    result = create_ask_user_tool_call(test_input)
    if result:
        print("✅ Tool call created successfully")
    else:
        print("❌ Failed to create tool call")

print("\nAll tests completed!") 