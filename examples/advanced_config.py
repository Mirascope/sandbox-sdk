"""Examples showing advanced configuration options."""

import json
import time

from sandbox import Sandbox

print("--- Example: Subprocess timeout ---")
sleep_script = "import time; time.sleep(2); print('Finished sleeping')"
short_timeout = 1.0  # seconds

try:
    with Sandbox(runner_type="subprocess", timeout=short_timeout) as sandbox:
        start = time.monotonic()
        result = sandbox.run(sleep_script)
        duration = time.monotonic() - start

        print(f"Execution finished after {duration:.2f} seconds.")
        if result.get("error") and "timed out" in result["error"]:
            print(f"Successfully timed out: {result['error']}")
        elif result.get("error"):
            print(f"Execution failed unexpectedly: {result['error']}")
        else:
            print(
                f"Execution succeeded unexpectedly? Stdout: {result.get('stdout', '')}"
            )

except FileNotFoundError:
    print("Skipping timeout test: 'uv' not found.")
except Exception as e:
    print(f"An error occurred: {e}")

print("\n" + "=" * 30 + "\n")

print("--- Example: Environment variable filtering ---")
env_script = """
import os, json
print(json.dumps({
    "MY_VAR": os.environ.get("MY_VAR"),
    "OTHER_VAR": os.environ.get("OTHER_VAR"),
    "SECRET": os.environ.get("SECRET"),
    "HOME": os.environ.get("HOME"),
    "PATH": os.environ.get("PATH"),
}))
"""
host_env = {
    "MY_VAR": "allowed_value",
    "OTHER_VAR": "also_allowed",
    "SECRET": "filtered",
}
allowed = ["MY_VAR", "OTHER_VAR", "HOME", "PATH"]

try:
    with Sandbox(
        runner_type="subprocess", environment=host_env, allowed_env_vars=allowed
    ) as sandbox:
        result = sandbox.run(env_script)

        if result.get("error"):
            print(
                f"Execution failed: {result['error']}\nStderr: {result.get('stderr', '')}"
            )
        elif result.get("stdout"):
            print("Environment variables inside sandbox:")
            try:
                env_in_sandbox = json.loads(result["stdout"])
                print(json.dumps(env_in_sandbox, indent=2))
                assert env_in_sandbox["MY_VAR"] == "allowed_value"
                assert env_in_sandbox["SECRET"] is None
                assert env_in_sandbox["HOME"] is not None
                print("\nEnvironment variable filtering successful.")
            except (json.JSONDecodeError, AssertionError, KeyError) as check_e:
                print(f"\nFailed to verify env vars: {check_e}")
                print(f"Raw stdout: {result['stdout']}")

except FileNotFoundError:
    print("Skipping env var test: 'uv' not found.")
except Exception as e:
    print(f"An error occurred: {e}")

print("\n" + "=" * 30 + "\n")

print("--- Example: Dependency with extras ---")
# Example using requests with SOCKS proxy support (installs PySocks)
requests_socks_code = """
import requests
import json

def check_socks_support():
    # Check if SOCKS support seems available via requests' internals
    # This indicates the 'socks' extra was likely installed (PySocks)
    try:
        from requests.adapters import SOCKSProxyManager # This exists if PySocks is importable by requests
        adapter_exists = hasattr(requests.adapters, 'SOCKSProxyManager')
        return {
            "requests_version": requests.__version__,
            "socks_adapter_found": adapter_exists,
            "note": "SOCKS adapter found indicates 'socks' extra likely installed." if adapter_exists else "SOCKS adapter not found."
        }
    except ImportError:
         return {"error": "Failed to import requests or SOCKS components."}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

# Note: We are not using print() inside the function for run_function
"""
# Specify dependency with version and extras
requests_deps = {
    # Use a reasonably recent version of requests
    "requests": {"version": "2.31.0", "extras": ["socks"]}
}

try:
    with Sandbox(deps=requests_deps) as sandbox:
        # Execute the function, no inputs needed
        result = sandbox.run_function(
            code=requests_socks_code,
            func_name="check_socks_support",  # Target the function
        )

        if result.get("error"):
            print(
                f"Execution failed: {result['error']}\nStderr: {result.get('stderr', '')}"
            )
        elif result.get("result") is not None:
            # Print the structured dictionary returned by the function
            print("Function output (parsed result):")
            print(json.dumps(result.get("result"), indent=2))
            # Verify the check passed
            assert result.get("result", {}).get("socks_adapter_found") is True
            print("\nDependency with extras seems to work.")
        else:
            print(f"Unexpected execution outcome: {result}")

except FileNotFoundError:
    print("Skipping dependency test: 'uv' not found.")
except Exception as e:
    print(f"An error occurred: {e}")
