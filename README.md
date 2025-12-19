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

###### Detailed explanation
> could you explain the last part of @test_sandbox.js is a json expression between ()

✦ The last part of test_sandbox.js uses parentheses to turn an Object Literal into an Expression. 

   1 ({
   2     status: "success",
   3     meta: { ... },
   4     mcp_call: { ... }
   5 });

  Here is the breakdown of why this is done:

  1. Avoiding Parser Ambiguity
  In JavaScript, if a line starts with {, the engine interprets it as a Block Statement (like an if block or a function
  body), not an object. 
   * { status: "success" } at the start of a line would cause a syntax error because the engine thinks status: is a label
     and "success" is a standalone string.
   * By wrapping it in (...), you force the parser to treat the contents as an expression. This ensures the engine
     recognizes it as an object literal.

  2. Returning a Value from the Sandbox
  This script is designed to be executed via a sandbox manager (likely using Node.js's vm module or eval()).
   * When you execute a script in a sandbox, the result of the last expression evaluated is typically returned to the host
     process.
   * By making this object the final expression, the sandbox "returns" this JSON-like object to the sandbox_executor.js.

  3. The "Proxy" Contract
  The comments in the file mention a "Proxy contract." This implies that the system calling this script expects a specific
  JSON structure to determine what to do next. In this case:
   * `mcp_call`: This is the instruction telling the host to execute the hello_name tool.
   * The sandbox itself doesn't have the permissions to call the tool directly; instead, it "hands off" the request to the
     more privileged Proxy by evaluating this object at the very end.

> what is the difference between using the () and return(ing) the object

✦ The primary difference is where the code is running and what the JavaScript engine allows.

  1. Context: Function vs. Script
   * `return` can only be used inside a function. If you put return { ... } at the top level of a standalone script file
     like test_sandbox.js, the engine will throw a SyntaxError: Illegal return statement.
   * `({ ... })` is an expression. In JavaScript, every script has a Completion Value (the result of the last line of code
     executed). Sandbox executors (like Node's vm module) capture this completion value as the result of the execution.

  2. How the Sandbox captures it
  When sandbox_executor.js runs this script, it likely does something like this:

   1 // Inside sandbox_executor.js (hypothetically)
   2 const result = vm.runInContext(code, context); 
   3 console.log(result.mcp_call.tool); // "hello_name"

  The vm module returns the result of the last expression. Since the script isn't wrapped in a function, the parentheses
  are used to ensure the object is treated as a value to be "passed back" to the executor.

  Summary Table


  ┌──────────────┬─────────────────────────────────────────────────┬──────────────────────────────────────────────────────
  ┐
  │ Feature      │ return { ... }                                  │ ({ ... })
  │
  ├──────────────┼─────────────────────────────────────────────────┼──────────────────────────────────────────────────────
  ┤
  │ Requirement  │ Must be inside a function.                      │ Can be anywhere (used as an expression).
  │
  │ **Top-lev... │ Fails (Syntax Error).                           │ Succeeds (Evaluates to the object).
  │
  │ Purpose      │ Ends function execution and passes a value.     │ Groups code into a single value/expression.
  │
  │ Sandbox Use  │ Used if the sandbox wraps your code in a fun... │ Used if the sandbox evaluates the script as a raw...
  │
  └──────────────┴─────────────────────────────────────────────────┴──────────────────────────────────────────────────────
  ┘


  In short: You use () because test_sandbox.js is a "naked" script. If you tried to use return, the script would crash
  before it even started.

> interesting!

✦ It is a clever pattern often seen in "Serverless" or "Plugin" architectures.

  Since you're working with a project that includes a sandbox_executor.js and a proxy.py, you are essentially looking at a
  multi-layered dispatch system:

   1. Python (`proxy.py`): Acts as the high-level manager.
   2. Node.js (`sandbox_executor.js`): Creates a secure, isolated "bubble."
   3. The Script (`test_sandbox.js`): Runs inside that bubble, does its logic, and "leaves" an object behind as its last
      act.

  If you'd like, I can examine sandbox_executor.js to show you exactly how it captures that object, or we can look at
  proxy.py to see how it handles the mcp_call that the sandbox requests



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
