import fetch from "node-fetch";

const MCP_URL = "https://your-zeabur-url.zeabur.app/mcp"; // REPLACE THIS

async function testMCP() {
  console.log("Testing MCP endpoint...\n");

  // 1. Initialize
  console.log("1. Initialize...");
  const initRes = await fetch(MCP_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: { name: "test", version: "1.0.0" }
      }
    })
  });
  console.log(`   Status: ${initRes.status}`);
  const initData = await initRes.json();
  console.log(`   Response:`, JSON.stringify(initData, null, 2));

  // 2. List tools
  console.log("\n2. List tools...");
  const listRes = await fetch(MCP_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/list",
      params: {}
    })
  });
  console.log(`   Status: ${listRes.status}`);
  const listData = await listRes.json();
  console.log(`   Tools: ${listData.result?.tools?.length || 0} tools found`);

  // 3. Call post_tweet
  console.log("\n3. Call post_tweet...");
  const postRes = await fetch(MCP_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 3,
      method: "tools/call",
      params: {
        name: "post_tweet",
        arguments: { text: "Test tweet from MCP! #testing" }
      }
    })
  });
  console.log(`   Status: ${postRes.status}`);
  const postData = await postRes.json();
  console.log(`   Response:`, JSON.stringify(postData, null, 2));
}

testMCP().catch(console.error);