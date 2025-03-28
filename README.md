# sandbox-sdk

A Python library for running code in isolated sandbox environments.

## Overview

sandbox-sdk provides a secure way to execute arbitrary Python code within isolated environments. It supports two execution backends (subprocess and Docker) and offers a simple interface for managing dependencies, environment variables, and resource limits.

## Installation

Basic installation:
```bash
pip install sandbox-sdk
```

If you want to use the Docker runner, install with the Docker extra:
```bash
pip install sandbox-sdk[docker]
```

Requirements:
- Python 3.10+
- `uv` command-line tool
- Docker (if using the Docker runner)

## Quick Start

```python
from sandbox import Sandbox

# Simple code block execution
with Sandbox(deps={"cowsay": "*"}) as sandbox:
    result = sandbox.run("import cowsay; cowsay.cow('Hello from sandbox!')")
    print(result["stdout"])

# Function execution with JSON I/O
with Sandbox(deps={"numpy": "*"}) as sandbox:
    result = sandbox.run_function(
        code="""
        import numpy as np
        
        def main(numbers):
            arr = np.array(numbers)
            return {
                "mean": float(arr.mean()),
                "sum": float(arr.sum())
            }
        """,
        inputs={"numbers": [1.5, 2.5, 3.0, 5.0]}
    )
    print(result["result"])  # {'mean': 3.0, 'sum': 12.0}
```

## Key Features

- **Two Execution Methods**:
  - **Code Block Method** (`run`): Execute complete Python scripts with captured outputs
  - **Function Method** (`run_function`): Execute specific functions with JSON inputs/outputs
  
- **Isolation**: Run untrusted code safely with configurable isolation levels
- **Dependency Management**: Specify required packages that will be installed within the sandbox environment
- **Multiple Runners**: Choose between subprocess (default) or Docker-based execution
- **Resource Controls**: Set execution timeouts and control network access
- **Environment Filtering**: Filter environment variables exposed to sandboxed code

## Execution Methods

sandbox-sdk provides two distinct execution methods for different use cases:

### 1. Code Block Method (`run`)

The `run` method executes a complete Python script and captures its standard output (stdout) and standard error (stderr).

```python
from sandbox import Sandbox

with Sandbox(deps={"requests": "*"}) as sandbox:
    result = sandbox.run("""
    import requests
    response = requests.get('https://httpbin.org/get')
    print("Status code:", response.status_code)
    print(response.json())
    """)
    
    # Access execution results
    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print("Output:")
        print(result["stdout"])
        
        if result["stderr"]:
            print("Errors/Warnings:")
            print(result["stderr"])
```

### 2. Function Method (`run_function`)

The `run_function` method executes a specific function and handles JSON-serializable inputs and outputs automatically.

```python
from sandbox import Sandbox

with Sandbox(deps={"numpy": ">=1.20"}) as sandbox:
    func_result = sandbox.run_function(
        code="""
        import numpy as np
        
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
        """,
        inputs={"numbers": [1.5, 2.5, 3.0, 5.0]},
        # func_name="main" is the default
    )
    
    # Access the function's return value
    if "result" in func_result:
        result_data = func_result["result"]
        print(f"Mean: {result_data['mean']}")
        print(f"Sum: {result_data['sum']}")
    else:
        print(f"Error: {func_result.get('error')}")
```

## Error Handling

sandbox-sdk provides detailed error information through the result dictionary. Here's how to handle common error scenarios:

### Script Errors

```python
from sandbox import Sandbox

with Sandbox() as sandbox:
    result = sandbox.run("""
    print("Starting script...")
    raise ValueError("Something went wrong!")
    print("This will never be printed.")
    """)
    
    # Check for runner errors
    if result.get("error"):
        print(f"Execution error: {result['error']}")
    
    # Access stdout (may contain partial output before error)
    print(f"Stdout: {result.get('stdout', '')}")
    
    # Access stderr (contains Python traceback)
    print(f"Stderr: {result.get('stderr', '')}")
```

### Function Errors

```python
from sandbox import Sandbox

with Sandbox() as sandbox:
    result = sandbox.run_function(
        code="""
        def main(data):
            if not isinstance(data, list):
                raise TypeError("Input must be a list")
            return sum(data)
        """,
        inputs={"data": "not a list"}  # Passing invalid input
    )
    
    # Check for errors (combined runner and script errors)
    if result.get("error"):
        print(f"Error: {result['error']}")
    elif "result" in result:
        print(f"Result: {result['result']}")
    else:
        print("Execution completed but returned no result or error.")
```

### Non-JSON Serializable Results

```python
from sandbox import Sandbox

with Sandbox() as sandbox:
    result = sandbox.run_function(
        code="""
        class MyObject:
            def __repr__(self):
                return "<MyObject instance>"
        
        def main():
            # This object cannot be directly serialized to JSON
            return MyObject()
        """
    )
    
    # This will report a serialization error
    if "error" in result and "not JSON serializable" in result["error"]:
        print("Detected non-serializable return value.")
    elif "result" in result:
        print(f"Result: {result['result']}")
```

## Advanced Usage

### Async Functions

You can execute asynchronous Python functions by setting the `is_async=True` flag:

```python
from sandbox import Sandbox

with Sandbox(deps={"asyncio": "*"}) as sandbox:
    result = sandbox.run_function(
        code="""
        import asyncio
        
        async def process_data_async(items, delay=0.1):
            results = []
            for i, item in enumerate(items):
                await asyncio.sleep(delay)  # Simulate async work
                results.append(f"Processed item {i}: {item * 2}")
            return {"processed": results}
        """,
        func_name="process_data_async",
        inputs={"items": ["a", "b", "c"], "delay": 0.05},
        is_async=True  # Important: enables async execution
    )
    
    if "result" in result:
        for item in result["result"]["processed"]:
            print(item)
```

### Dependencies with Extras

You can specify package extras using a dictionary format:

```python
from sandbox import Sandbox

# Request with SOCKS proxy support (installs PySocks)
socks_deps = {
    "requests": {"version": "2.31.0", "extras": ["socks"]}
}

with Sandbox(deps=socks_deps) as sandbox:
    # The code will have access to requests with SOCKS support
    result = sandbox.run_function(
        code="""
        def check_socks_support():
            import requests
            # Check if SOCKS support seems available
            adapter_exists = hasattr(requests.adapters, 'SOCKSProxyManager')
            return {
                "requests_version": requests.__version__,
                "socks_adapter_found": adapter_exists
            }
        """
    )
    print(result["result"])  # Should show socks_adapter_found: true
```

### Timeout Configuration

Set execution timeouts to prevent long-running code:

```python
from sandbox import Sandbox

with Sandbox(timeout=1.0) as sandbox:  # 1 second timeout
    result = sandbox.run("import time; time.sleep(2); print('Done')")
    
    if result.get("error") and "timed out" in result["error"]:
        print("Successfully enforced timeout")
```

### Environment Variable Control

Control which environment variables are accessible in the sandbox:

```python
from sandbox import Sandbox

# Define environment variables to expose to the sandbox
env = {
    "MY_VAR": "allowed_value",
    "SECRET": "should_be_filtered"
}

# Specify which variables are allowed
allowed_vars = ["MY_VAR", "HOME", "PATH"]

with Sandbox(environment=env, allowed_env_vars=allowed_vars) as sandbox:
    result = sandbox.run("""
    import os, json
    print(json.dumps({
        "MY_VAR": os.environ.get("MY_VAR"),
        "SECRET": os.environ.get("SECRET")  # Will be None
    }))
    """)
    
    # Only MY_VAR should be present, SECRET should be None
    print(result["stdout"])
```

## Docker Runner

For stronger isolation, you can use the Docker runner which executes code inside a container.

**Note:** To use the Docker runner, you must install the package with the Docker extra:
```bash
pip install sandbox-sdk[docker]
```

This installs the required `docker` Python package (version 7.1.0 or newer).

### Basic Docker Usage

```python
from sandbox import Sandbox

with Sandbox(runner_type="docker", deps={"numpy": "*"}) as sandbox:
    result = sandbox.run("import numpy; print(numpy.__version__)")
    print(result["stdout"])
```

### Network Access Control

By default, network access is disabled in Docker mode:

```python
from sandbox import Sandbox

# With network disabled (default)
with Sandbox(runner_type="docker") as sandbox:
    result = sandbox.run("""
    import socket, json
    try:
        socket.gethostbyname('example.com')
        print(json.dumps({"network": True}))
    except socket.gaierror:
        print(json.dumps({"network": False}))
    """)
    # Should print: {"network": False}
    print(result["stdout"])
    
# With network enabled
with Sandbox(runner_type="docker", allow_network=True, deps={"requests": "*"}) as sandbox:
    result = sandbox.run_function(
        code="""
        def main(url):
            import requests
            response = requests.get(url, timeout=5)
            return {"status_code": response.status_code}
        """, 
        inputs={"url": "https://example.com"}
    )
    # Should return status code 200 if network is working
    print(result["result"])
```

### Custom Docker Images

You can specify a custom Docker image:

```python
from sandbox import Sandbox

with Sandbox(
    runner_type="docker",
    runner_kwargs={
        "image": "ghcr.io/astral-sh/uv:python3.13-alpine",
        "container_kwargs": {
            "mem_limit": "256m",
            "cpu_quota": 50000
        }
    }
) as sandbox:
    result = sandbox.run(
        "import platform; print(f'Python {platform.python_version()}')"
    )
    print(result["stdout"])  # Should show Python 3.13.x
```

## Reference

### Sandbox Class Options

```python
sandbox = Sandbox(
    # Required Python packages (name -> version specifier)
    deps={
        "simple_package": "*",                    # Any version 
        "versioned_package": ">=1.0.0,<2.0.0",    # Version range
        "package_with_extras": {                  # With extras and version
            "version": "1.2.3",
            "extras": ["feature1", "feature2"]
        }
    },
    
    # Runner type: "subprocess" (default) or "docker"
    runner_type="subprocess",
    
    # Execution timeout in seconds (default: 60.0)
    timeout=30.0,
    
    # Allow network access (primarily for Docker runner)
    allow_network=False,
    
    # Environment variables to pass into sandbox
    environment={"API_KEY": "my_key", "DEBUG": "1"},
    
    # Whitelist of allowed environment variables
    allowed_env_vars=["HOME", "PATH", "API_KEY", "DEBUG"],
    
    # Additional runner-specific options
    runner_kwargs={},
)
```

### Result Dictionary

Both `run()` and `run_function()` methods return a dictionary with the following keys:

| Key | Description |
| --- | ----------- |
| `stdout` | Standard output captured from the execution |
| `stderr` | Standard error captured from the execution (includes tracebacks) |
| `error` | Error message if the execution failed (combines runner and script errors) |
| `result` | Only present in `run_function()` - contains the function's JSON-serialized return value |

### Security Considerations

- The subprocess runner provides basic isolation but inherits the host's network access
- The Docker runner offers stronger isolation with optional network restrictions
- Environment variables are filtered through an allow-list to prevent leaking sensitive information
- Execution timeout helps prevent resource exhaustion attacks
- Proper resource limits should be configured when running potentially untrusted code

## Example Files

The package includes several example files demonstrating common usage patterns:

- `examples/run_script.py` - Basic usage of `sandbox.run()`
- `examples/run_function_example.py` - Basic usage of `sandbox.run_function()`
- `examples/async_function.py` - Using async functions with `is_async=True`
- `examples/error_handling.py` - Handling various error scenarios
- `examples/advanced_config.py` - Advanced configuration options
- `examples/docker_usage.py` - Using the Docker runner