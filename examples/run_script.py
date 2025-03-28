"""Example demonstrating the basic usage of Sandbox.run()."""

from sandbox import Sandbox

# Dependencies required by the script
script_deps = {"cowsay": "*"}
# The script to execute (prints to stdout)
script_code = "import cowsay; cowsay.cow('Hello from sandbox.run!')"

print("--- Running script using sandbox.run() ---")

try:
    # Initialize Sandbox with dependencies
    with Sandbox(deps=script_deps) as sandbox:
        # Execute the script block
        result = sandbox.run(script_code)

        # Check for runner/execution errors
        if result.get("error"):
            print(f"Execution failed: {result['error']}")
            print(f"Stderr: {result.get('stderr', '')}")
        else:
            # Print the captured standard output
            print("Script executed successfully. Output:")
            print(result.get("stdout", ""))

except FileNotFoundError:
    print("Error: 'uv' command not found. Please ensure uv is installed and in PATH.")
except Exception as e:
    print(f"An error occurred: {e}")
