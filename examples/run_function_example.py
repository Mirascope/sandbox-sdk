"""Example demonstrating the usage of Sandbox.run_function()."""

import json

from sandbox import Sandbox

# Python code containing the function definition
function_code = """
import numpy as np

# Function to execute (defaults to 'main')
def main(numbers: list[float]):
    arr = np.array(numbers)
    if len(arr) == 0:
        # Errors can be returned in the JSON result
        return {"error": "Input list cannot be empty"}
    # Return a JSON serializable dictionary
    return {
        "input_list": numbers,
        "mean": arr.mean(),
        "sum": arr.sum()
    }
"""
# Dependencies required by the function
function_deps = {"numpy": ">=1.20"}
# Input data for the function
function_inputs = {"numbers": [1.5, 2.5, 3.0, 5.0]}

print("--- Running function using sandbox.run_function() ---")

try:
    # Initialize Sandbox with dependencies
    with Sandbox(deps=function_deps) as sandbox:
        # Execute the 'main' function defined in 'function_code'
        result = sandbox.run_function(
            code=function_code,
            inputs=function_inputs,
            # func_name="main" is the default
        )

        # Check for runner errors first
        if result.get("error") and "Script Error" not in result["error"]:
            print(f"Runner execution failed: {result['error']}")
            print(f"Stderr: {result.get('stderr', '')}")
        else:
            # Check for errors reported *by the executed function* (in the JSON)
            script_result = result.get("result")
            script_error = result.get("error")  # Contains combined runner/script errors

            if script_error:
                print(f"Execution reported an error:\n{script_error}")
                if result.get("stderr"):
                    print(f"\nCaptured Stderr:\n{result['stderr']}")
            elif script_result is not None:
                # Successfully got a result from the function
                print("Function executed successfully. Result:")
                print(json.dumps(script_result, indent=2))
            else:
                # Should not happen if no error, but handle defensively
                print("Execution finished, but no result or error was captured.")
                print(f"Stdout: {result.get('stdout', '')}")
                print(f"Stderr: {result.get('stderr', '')}")

except FileNotFoundError:
    print("Error: 'uv' command not found. Please ensure uv is installed and in PATH.")
except Exception as e:
    print(f"An error occurred: {e}")
