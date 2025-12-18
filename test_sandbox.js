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

// Internal logic: decide which name to use
const userName = "Sandboxed-User";

console.log("Logic complete. Requesting MCP tool call via Proxy...");

// The Proxy contract: the last expression evaluated should be the result object
// If 'mcp_call' is present, the Proxy will execute it.
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
