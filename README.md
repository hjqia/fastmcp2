## Local
### Install
Install uv if not install
In repo root dir
uv pip install -e .    (this should create a venv if none exists)


### Run the server and the client locally
python src/http_mcp_server.py   (listens at port 8000 by default)

To probe server connection:
python src/http_mcp_client.py --probe
python src/http_mcp_client.py --probe --bearer-token  $BEARER_TOKEN

(bearer-token flag could be required for all the below commands when connecting to remote services such as Blaxel)

To list server tools:
python src/ttp_mcp_client.py --tool list

To run a specific tool:
python src/http_mcp_client.py --tool slow_task --duration 5
or,
python src/http_mcp_client.py --tool choose_action

To upload a local file:
python src/http_mcp_client.py --tool receive_file --upload-file /path/to/file.ext

The `receive_file` tool accepts an MCP resource attachment (embedded resource or resource link). Uploaded files are stored in `/tmp/mcp_uploads` by default; set `UPLOAD_DIR` to change where files are written.

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
export BEARER_TOKEN=""
export SERVER_URL="https://run.blaxel.ai/momrose/functions/fastmcp2/mcp"
python src/ttp_mcp_client.py --tool list --bearer-token  $BEARER_TOKEN
