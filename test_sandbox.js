// test_sandbox.js
/**
 * Cloudflare-style Sandbox Script
 * 
 * This script runs inside the Node.js sandbox.
 * It performs some internal logic and then returns an instruction
 * to the Proxy to call a specific MCP tool.
 */

console.log("--- Sandbox Execution Internal Logs ---");
console.log("Initializing sandbox environment...");

const platform = "Cloudflare Simulation";
const timestamp = new Date().toISOString();

console.log(`Running on ${platform} at ${timestamp}`);

// LLM who created this code or the same current code decides which name to use
const userName = "Sandboxed-User";

console.log("Logic complete. Requesting MCP tool call via Proxy...");

// LLM who created this code or the same current code decides which tool to use
// In The Proxy script: the last expression evaluated by the executor script is the result object that is equal to this expression
({
    status: "success",
    meta: {
        platform: platform,
        runtime: "Node.js VM"
    },
    mcp_call: {
        tool: "hello_name",
        arguments: {
            name: userName
        }
    }
});
// If 'mcp_call' is present, the Proxy will execute it using tool (name) and arguments.
