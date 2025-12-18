# Using a file (Cleaner approach):

# test_local.py
from mcp_proxies.mcp_server import hello_name, slow_task, choose_action

print("\nHello...")
action = hello_name(name='ache')
print(f"Answer: {action}")

print("Starting slow task...")
result = slow_task(duration=3)
print(f"Server says: {result}")

print("\nAsking for action...")
action = choose_action()
print(f"User picked: {action}")

# python src/http_mcp_client.py --execute-local --script test_local.py
