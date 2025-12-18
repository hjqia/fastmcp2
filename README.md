## Local
### Install
Install uv if not install
In repo root dir
uv pip install -e .    (this should create a venv if none exists)


### Run the server and the client locally
python src/http_mcp_server.py   (listens at port 8000 by default)

#### To probe server connection:
python src/http_mcp_client.py --probe
python src/http_mcp_client.py --probe --bearer-token  $BEARER_TOKEN

(bearer-token flag could be required for all the below commands when connecting to remote services such as Blaxel)

#### To list server tools:
python src/ttp_mcp_client.py --tool list

#### To run a specific tool:
python src/http_mcp_client.py --tool slow_task --duration 5
or,
python src/http_mcp_client.py --tool choose_action

#### To upload a local file:
python src/http_mcp_client.py --tool receive_file --upload-file /path/to/file.ext

The `receive_file` tool accepts an MCP resource attachment (embedded resource or resource link). Uploaded files are stored in `/tmp/mcp_uploads` by default; set `UPLOAD_DIR` to change where files are written.


#### To execute code:
Assisted by Gemini (Conversation checkpoint saved with tag: code_execution.md.)

UNSAFE OPTION: RUN ANY CODE IN SERVER
python src/http_mcp_client.py --tool run_python --script "import os; print(os.getcwd())"

Run a file:

Create a dummy script
echo "print('Hello from file!')" > test_script.py
python src/http_mcp_client.py --tool run_python --script test_script.py


ANTHROPIC APPROACH: RUN CODE LOCALLY
https://www.anthropic.com/engineering/code-execution-with-mcp

python src/http_mcp_client.py --generate
python src/http_mcp_client.py --execute-local --script "from mcp_proxies.mcp_server import slow_task;print(slow_task(duration=2))"
python src/http_mcp_client.py --execute-local --script test_local.py


CLOUDFARE APPROACH: USE PROXY TO RUN CODE IN SANDBOX
https://blog.cloudflare.com/code-mode/
https://github.com/jx-codes/lootbox

node sandbox_executor.js
Sandbox Executor (Node.js) running on port 8080

python proxy.py --script "console.log('Sandbox started'); const output = { mcp_call: { tool: 'hello_name', arguments: { name:'Cloudflare' } } }; output;"

OR

python proxy.py --script test_sandbox.js

  1. `proxy.py` reads test_sandbox.js.
   2. `proxy.py` POSTs the code to `sandbox_executor.js` (running on port 8080).
   3. `sandbox_executor.js` runs it in a vm context, captures the logs (Initialization, platform info), and returns the final object.
   4. `proxy.py` prints the logs and the final result.
   5. `proxy.py` notices the mcp_call instruction, connects to the MCP Server (on port 1338), and calls
      hello_name(name="Sandboxed-User").
   6. `proxy.py` prints the final greeting from the server.



## Blaxel
### Create and test Docker image
Still in repo's root: run uv lock
docker build -t blaxel-mcp2-app .
docker run -p 1338:1338 blaxel-mcp2-app 

python src/http_mcp_client.py --tool list


### Deploy
Still in repo's root:
Install the Blaxel's bl app

Edit the blaxel.toml if required

Run: bl deploy
(It verifies, builds and uploads the Docker image, then run the mcp server in their platform using the name set in blaxel.toml)

You can monitor instance using:
bl logs functions fastmcp2 -f   (-f for continuous logging)

### Test
unset BEARER_TOKEN
export BEARER_TOKEN='blahblahblah"
export SERVER_URL="https://run.blaxel.ai/momrose/functions/fastmcp2/mcp"
python src/ttp_mcp_client.py --tool list --bearer-token  $BEARER_TOKEN
