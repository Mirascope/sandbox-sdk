"""Example using sandbox.run_function() with an async function."""

import json

from sandbox import Sandbox

async_code = """
import asyncio

async def process_data_async(items: list, delay: float = 0.1):
    results = []
    for i, item in enumerate(items):
        await asyncio.sleep(delay) # Simulate async work
        results.append(f"Processed item {i}: {item * 2}")
    return {"processed": results}

# Note: 'main' is the default func_name, but we explicitly use 'process_data_async'
"""
# Inputs for the async function
async_inputs = {"items": ["a", "b", "c"], "delay": 0.05}

print("--- Running async function using sandbox.run_function() ---")

try:
    with Sandbox() as sandbox:  # No external deps needed for this example
        # Execute the async function, setting is_async=True
        result = sandbox.run_function(
            code=async_code,
            func_name="process_data_async",  # Specify the async function name
            inputs=async_inputs,
            is_async=True,  # IMPORTANT: Set this flag for async functions
        )

        if result.get("error"):
            print(f"Execution Error:\n{result['error']}")
            if result.get("stderr"):
                print(f"Stderr:\n{result['stderr']}")
        elif result.get("result") is not None:
            print("Async function Result:")
            print(json.dumps(result["result"], indent=2))
        else:
            print("Execution finished without error, but no result captured.")

except FileNotFoundError:
    print("Error: 'uv' command not found. Please ensure uv is installed and in PATH.")
except Exception as e:
    print(f"An error occurred: {e}")
