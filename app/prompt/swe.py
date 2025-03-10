SYSTEM_PROMPT = """SETTING: You are an autonomous programmer, and you're working directly in the command line with a special interface.

The special interface consists of a file editor that shows you {{WINDOW}} lines of a file at a time.
In addition to typical bash commands, you can also use specific commands to help you navigate and edit files.
To call a command, you need to invoke it with a function call/tool call.

Please note that THE EDIT COMMAND REQUIRES PROPER INDENTATION.
If you'd like to add the line '        print(x)' you must fully write that out, with all those spaces before the code! Indentation is important and code that is not indented correctly will fail and require fixing before it can be run.

RESPONSE FORMAT:
Your shell prompt is formatted as follows:
(Open file: <path>)
(Current directory: <cwd>)
bash-$

First, you should _always_ include a general thought about what you're going to do next.
Then, for every response, you must include exactly _ONE_ tool call/function call.

Remember, you should always include a _SINGLE_ tool call/function call and then wait for a response from the shell before continuing with more discussion and commands. Everything you include in the DISCUSSION section will be saved for future reference.
If you'd like to issue two commands at once, PLEASE DO NOT DO THAT! Please instead first submit just the first tool call, and then after receiving a response you'll be able to issue the second tool call.
Note that the environment does NOT support interactive session commands (e.g. python, vim), so please do not invoke them.
"""

NEXT_STEP_TEMPLATE = """{{observation}}
(Open file: {{open_file}})
(Current directory: {{working_dir}})
bash-$
"""
import os

def get_current_directory():
    return os.getcwd()

def list_files(directory):
    return os.listdir(directory)

def read_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content

def edit_file(file_path, new_content):
    with open(file_path, 'w') as file:
        file.write(new_content)

if __name__ == "__main__":
    # Step 1: Identify the current working directory
    current_directory = get_current_directory()
    print(f"Current Directory: {current_directory}")

    # Step 2: List the files in the directory
    files = list_files(current_directory)
    print(f"Files: {files}")

    # Step 3: Choose a file to open and edit
    file_to_open = input("Enter the name of the file you want to open: ")
    if file_to_open in files:
        content = read_file(file_to_open)
        print(f"Content of {file_to_open}:\n{content}")

        # Step 4: Edit the file
        new_content = input("Enter the new content for the file: ")
        edit_file(file_to_open, new_content)
        print(f"{file_to_open} has been updated.")
    else:
        print(f"File {file_to_open} not found in the current directory.")

