"""Examples demonstrating error handling in sandbox-sdk."""

from sandbox import Sandbox

print("--- Example: Handling script error in sandbox.run() ---")
error_script = """
print("Script starting...")
raise ValueError("Something went wrong!")
print("This will not be printed.")
"""
try:
    with Sandbox() as sandbox:
        result = sandbox.run(error_script)
        print(f"Stdout: {result.get('stdout', '')!r}")  # May be empty or partial
        print(f"Stderr: {result.get('stderr', '')!r}")  # Should contain traceback
        print(
            f"Error reported by runner: {result.get('error')}"
        )  # Runner error (e.g., exit code)
except Exception as e:
    print(f"Sandbox setup error: {e}")

print("\n" + "=" * 30 + "\n")

print("--- Example: Handling function error in sandbox.run_function() ---")
func_error_code = """
def main(data):
    if not isinstance(data, list):
        raise TypeError("Input must be a list")
    return sum(data)
"""
try:
    with Sandbox() as sandbox:
        # Pass invalid input to trigger TypeError
        result = sandbox.run_function(func_error_code, inputs={"data": "not a list"})

        print(f"Result field: {result.get('result')}")  # Should be None
        print(
            f"Error field (combined): {result.get('error')}"
        )  # Should contain script error
        print(
            f"Stderr field: {result.get('stderr', '')!r}"
        )  # May contain traceback from wrapper
except Exception as e:
    print(f"Sandbox setup error: {e}")

print("\n" + "=" * 30 + "\n")

print("--- Example: Handling non-JSON serializable result ---")
non_json_code = """
class MyObject:
    def __repr__(self):
        return "<MyObject instance>"

def main():
    # This object cannot be directly serialized to JSON
    return MyObject()
"""
try:
    with Sandbox() as sandbox:
        result = sandbox.run_function(non_json_code)

        print(f"Result field: {result.get('result')}")  # None
        print(
            f"Error field: {result.get('error')}"
        )  # Should indicate serialization error
        print(
            f"Stderr field: {result.get('stderr', '')!r}"
        )  # May contain serialization error details
except Exception as e:
    print(f"Sandbox setup error: {e}")

print("\n" + "=" * 30 + "\n")

print(
    "--- Example: Handling invalid JSON output from script (if run_function used) ---"
)
invalid_json_code = """
# This script is intended for run_function, but prints invalid JSON
print("This is not valid JSON {")

def main(): # Define main so run_function doesn't fail on generation
    return 1
"""
try:
    with Sandbox() as sandbox:
        # Normally run_function expects JSON output, but runner captures raw stdout
        result = sandbox.run_function(invalid_json_code)

        print(f"Result field: {result.get('result')}")  # None
        print(f"Error field: {result.get('error')}")  # Should indicate JSON parse error
        print(
            f"Stdout field: {result.get('stdout', '')!r}"
        )  # Contains the invalid output
except Exception as e:
    print(f"Sandbox setup error: {e}")
