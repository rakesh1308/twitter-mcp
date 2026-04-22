const MCP_URL = "https://twitter13.zeabur.app";

async function test() {
  console.log("Testing Zeabur MCP Server...\n");

  // 1. Health check
  console.log("1. Health check...");
  try {
    const health = await fetch(`${MCP_URL}/health`);
    const healthData = await health.json();
    console.log(`   Status: ${health.status}`);
    console.log(`   Response:`, JSON.stringify(healthData, null, 2));
  } catch (e) {
    console.log(`   Error: ${e.message}`);
  }

  // 2. Initialize
  console.log("\n2. Initialize...");
  try {
    const init = await fetch(`${MCP_URL}/mcp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 1, method: "initialize",
        params: { protocolVersion: "2025-03-26", capabilities: {}, clientInfo: { name: "test", version: "1.0.0" } }
      })
    });
    const initData = await init.json();
    console.log(`   Status: ${init.status}`);
    console.log(`   Response:`, JSON.stringify(initData, null, 2));
  } catch (e) {
    console.log(`   Error: ${e.message}`);
  }

  // 3. List tools
  console.log("\n3. List tools...");
  try {
    const list = await fetch(`${MCP_URL}/mcp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} })
    });
    const listData = await list.json();
    console.log(`   Status: ${list.status}`);
    console.log(`   Tools: ${listData.result?.tools?.length || 0}`);
  } catch (e) {
    console.log(`   Error: ${e.message}`);
  }

  // 4. Post tweet
  console.log("\n4. Post tweet...");
  try {
    const post = await fetch(`${MCP_URL}/mcp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 3, method: "tools/call",
        params: { name: "post_tweet", arguments: { text: "Test from remote!" } }
      })
    });
    const postData = await post.json();
    console.log(`   Status: ${post.status}`);
    console.log(`   Response:`, JSON.stringify(postData, null, 2));
  } catch (e) {
    console.log(`   Error: ${e.message}`);
  }
}

test();