import OAuth from "oauth-1.0a";
import * as crypto from "crypto";

const account1 = {
  name: "GrowthDigest",
  apiKey: "iKwt24xxKEsvR9CGTjN9uKjVP",
  apiSecret: "G6UicVC8NHRhvlyGTwdqXzMWZIciuztTYg1MKOqPiT2AQB1Unm",
  accessToken: "1553016958010130432-kEwdaLW0nFHfOiS51FUV9QHEgBTBRG",
  accessTokenSecret: "Ufug5CkLMOMKWYsN2LWqjoANAlV5vTP8dY71KW9WdX1HA",
};

const account2 = {
  name: "noetic_rakesh",
  apiKey: "5xFakqtBv7Xm3qpk6NWDUu9ZN",
  apiSecret: "lW4JwUG3yDyLEv9Kr2CqaBZoINnC2uT2xysz1ytDkiiIJsO0tM",
  accessToken: "2013235685470408704-jc7ytjQSCkDHfVYZXaAEjoOqveY51o",
  accessTokenSecret: "3KYQqkqnT6rH0ORdeej7PJ3YtBeFwEp9bT0NiE45ziun8",
};

async function testAccount(creds) {
  const oauth = new OAuth({
    consumer: { key: creds.apiKey, secret: creds.apiSecret },
    signature_method: "HMAC-SHA1",
    hash_function: (baseString, key) => {
      const hmac = crypto.createHmac("sha1", key);
      hmac.update(baseString);
      return hmac.digest("base64");
    },
  });

  const url = `https://api.twitter.com/2/users/by/username/${creds.name}`;
  const auth = oauth.authorize({ url, method: "GET" }, { key: creds.accessToken, secret: creds.accessTokenSecret });
  
  const res = await fetch(url, {
    method: "GET",
    headers: { Authorization: oauth.toHeader(auth).Authorization, "Content-Type": "application/json" },
  });
  
  if (res.ok) {
    const data = await res.json();
    const metrics = data.data.public_metrics || {};
    console.log(`✅ ${creds.name}: ${res.status} - @${data.data.username} (${metrics.followers_count || '?'} followers)`);
  } else {
    const data = await res.json();
    console.log(`❌ ${creds.name}: ${res.status} - ${JSON.stringify(data)}`);
  }
}

console.log("Verifying credentials...\n");
await testAccount(account1);
await testAccount(account2);
console.log("\nDone!");