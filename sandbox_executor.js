const http = require('http');
const vm = require('vm');

const PORT = 8080;

const server = http.createServer((req, res) => {
    if (req.method !== 'POST' || req.url !== '/execute') {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Not Found' }));
        return;
    }

    let body = '';
    req.on('data', chunk => {
        body += chunk.toString();
    });

    req.on('end', () => {
        try {
            const data = JSON.parse(body);
            const code = data.code;

            if (!code) {
                res.writeHead(400, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'No code provided' }));
                return;
            }

            console.log('--- [Sandbox] Executing code ---');
            
            // Capture console.log
            let logs = [];
            const sandboxConsole = {
                log: (...args) => logs.push(args.map(a => String(a)).join(' ')),
                error: (...args) => logs.push('ERROR: ' + args.map(a => String(a)).join(' '))
            };

            const context = vm.createContext({
                console: sandboxConsole,
                // Add other safe globals if needed
            });

            let result;
            try {
                // Execute code
                result = vm.runInContext(code, context, { timeout: 1000 });
            } catch (execError) {
                logs.push(`Runtime Error: ${execError.message}`);
                result = null;
            }

            const response = {
                result: result,
                logs: logs,
                status: 'success'
            };

            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(response));
            console.log('--- [Sandbox] Execution complete ---');

        } catch (e) {
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: e.message }));
        }
    });
});

server.listen(PORT, () => {
    console.log(`Sandbox Executor (Node.js) running on port ${PORT}`);
});
