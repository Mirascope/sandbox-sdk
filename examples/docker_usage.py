"""Examples using the Docker runner."""

from sandbox import Sandbox

print("--- Example: Using Docker runner with network disabled (default) ---")
network_code = """
import socket, json
try:
    socket.gethostbyname('example.com')
    print(json.dumps({"network": True})) # This shouldn't happen by default
except socket.gaierror:
    print(json.dumps({"network": False}))
except Exception as e:
    print(json.dumps({"error": str(e)}))

def main(): # Define main for run_function call
    pass # Function itself doesn't need to do anything here
"""
try:
    with Sandbox(runner_type="docker") as sandbox:  # allow_network=False is default
        result = sandbox.run_function(
            network_code
        )  # Use run_function to get parsed result
        if result.get("error"):
            print(f"Error: {result['error']}")
        elif result.get("result"):
            print(
                f"Network access result (default): {result['result']}"
            )  # Expect {"network": False}
        else:
            print(f"Unexpected result: {result}")

except Exception as e:
    print(f"An error occurred: {e}")

print("\n" + "=" * 30 + "\n")

print("--- Example: Using Docker runner with network enabled ---")
network_deps = {"requests": "*"}
network_func_code = """
import requests
def main(url):
    try:
        response = requests.get(url, timeout=5)
        return {"status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
"""
try:
    with Sandbox(
        runner_type="docker", deps=network_deps, allow_network=True
    ) as sandbox:
        result = sandbox.run_function(
            network_func_code, inputs={"url": "https://example.com"}
        )
        if result.get("error"):
            print(f"Error: {result['error']}")
        elif result.get("result"):
            print(
                f"Network access result (enabled): {result['result']}"
            )  # Expect {'status_code': 200} or error
        else:
            print(f"Unexpected result: {result}")

except Exception as e:
    print(f"An error occurred: {e}")

print("\n" + "=" * 30 + "\n")

print("--- Example: Using a custom Docker image ---")
custom_image = "ghcr.io/astral-sh/uv:python3.13-alpine"
simple_print_code = "import platform; print(f'Running on {platform.system()} Python {platform.python_version()}')"
try:
    with Sandbox(
        runner_type="docker", runner_kwargs={"image": custom_image}
    ) as sandbox:
        result = sandbox.run(simple_print_code)
        if result.get("error"):
            print(f"Error with custom image: {result['error']}")
            print(f"Stderr: {result.get('stderr', '')}")
        else:
            print(f"Output from custom image:\n{result.get('stdout', '')}")
except Exception as e:
    print(f"An error occurred setting up custom image sandbox: {e}")
