# Remote MCP troubleshooting (Lambda + Claude / mcp-remote)

Use this after deploy or when clients report **502**, **500**, or **timeouts** on `POST /mcp`.

See also: [DEPLOY.md](DEPLOY.md) (redeploy), [README_REMOTE_MCP.md](../README_REMOTE_MCP.md) (auth modes).

## Redeploy checklist (ZIP stack)

From the **repository root**, with AWS CLI credentials configured:

```bash
export OVALEDGE_BASE_URL=https://your-pod.ovaledge.cloud/ovaledge   # no trailing slash issues — script trims
export STACK_NAME=oe-mcp-zip                                        # or your existing stack name
export AWS_REGION=us-east-1
export AUTH_MODE=remote_credentials
export LAMBDA_MEMORY_SIZE=1024                                      # default in template; raise if OOM in logs
export LAMBDA_TIMEOUT=30                                            # HTTP API max integration is 30s

./scripts/deploy.sh --zip
```

After deploy:

1. Copy **`MCPEndpointUrl`** from stack outputs into the client (`mcp-remote` URL ends with `/mcp`).
2. Set Lambda env **`MCP_PUBLIC_BASE_URL`** = output **`MCPPublicBaseUrl`** (host only, no `/mcp`).
3. Toggle the MCP server off/on in the client so it reconnects.
4. Verify health:

   ```bash
   curl -sS "https://<api-id>.execute-api.<region>.amazonaws.com/health" | jq .
   ```

   Expect `"status": "healthy"` and `"mcp_lifespan_ready": true` on warm Lambda instances.

5. Validate OvalEdge token exchange (same credentials as client headers):

   ```bash
   export AUTH_MODE=remote_credentials
   export OVALEDGE_BASE_URL=https://your-pod.ovaledge.cloud/ovaledge
   export OVALEDGE_USER_TOKEN='...'
   export OVALEDGE_USER_SECRET='...'
   poetry run python scripts/validate_remote_mcp.py --credentials
   ```

**Stale stack URL:** If the client still points at an old `*.execute-api.*.amazonaws.com` host and DNS fails (`ENOTFOUND`), update the URL from current stack outputs — API IDs change when stacks are recreated.

## Error patterns

| Client / log symptom | Likely cause | What to check |
| -------------------- | ------------ | ------------- |
| **502** `token exchange returned an empty body (HTTP 200)` | OvalEdge `POST /api/user/token/generate` returned no JWT | Credentials, `OVALEDGE_BASE_URL`, OvalEdge pod health; run `validate_remote_mcp.py --credentials` |
| **502** `user-cred exchange failed: 503` | OvalEdge temporarily unavailable | Retry; check OvalEdge load balancer / app logs |
| **502** on first `initialize` only | Auth middleware before MCP | Same as token exchange; not an MCP tool bug |
| **500** `{"message":"Internal Server Error"}` on `tools/call` | Lambda exception, timeout, or MCP lifespan | CloudWatch (below); `/health` `mcp_lifespan_ready`; redeploy latest code |
| **ENOTFOUND** on API hostname | Wrong / deleted API Gateway | Update client URL from stack `MCPEndpointUrl` |
| **MCP error -32001: Request timed out** (client) | Request exceeded client timeout (often 4 min) while server hung or retried | CloudWatch duration; OvalEdge slowness; reduce `depth` on lineage |
| Pydantic `Unexpected keyword argument` on tools | Client using old parameter names (`query` vs `search_terms`) | Redeploy server; use current tool schema from `tools/list` |
| Server instructions say **Phase 1 read-only** only | Old Lambda artifact | Redeploy from current `main` / feature branch |

## CloudWatch Logs

Log group (default): `/aws/lambda/<StackName>-<Environment>-lambda`

### Useful filter patterns

**Failed MCP HTTP (5xx):**

```
"mcp_http" "status=5"
```

**Slow or failed tool invocations:**

```
"mcp_tool"
```

**Token exchange / auth:**

```
"token exchange" OR "OvalEdge token exchange" OR "upstream failure"
```

**Lambda handler crashes:**

```
"Lambda handler uncaught error"
```

**MCP lifespan (cold start):**

```
"StreamableHTTPSessionManager did not start within"
"MCP HTTP lifespan"
```

Lambda pins FastMCP streamable HTTP during **import** (eager bootstrap) and again on each invoke if needed. Tunables:

| Env var | Default | Purpose |
|---------|---------|---------|
| `LAMBDA_MCP_LIFESPAN_STARTUP_TIMEOUT_SECONDS` | `28` | Max wait for holder task during INIT / first invoke |
| `LAMBDA_MCP_LIFESPAN_EAGER_BOOTSTRAP` | `true` | Pin lifespan during Lambda import (adds to Init, avoids 15s first-request failures) |

If cold starts still time out, raise memory (`LambdaMemorySize=1024` in deploy) and ensure Lambda timeout is **30s** (API Gateway max).

### Example Insights query (tool duration)

```
fields @timestamp, @message
| filter @message like /mcp_tool/
| sort @timestamp desc
| limit 50
```

Log lines intentionally **omit** credential headers. Tool logs include `tool=<name>`, `duration_ms`, and a short argument summary (`object_id`, `search_terms`, etc.).

## Performance notes

- **HTTP API + Lambda** integration timeout is **30 seconds**. Increasing Lambda timeout above 30s does not extend API Gateway’s wait for `/mcp`.
- **Large responses** (`asset_lineage`, `search_platform_docs`, fat `catalog_asset_details`) need CPU/memory to serialize. Default template memory is now **1024 MB**; raise with `LAMBDA_MEMORY_SIZE=2048` if CloudWatch shows duration near 30s or memory maxed.
- **Intermittent 500s** with successful retries often indicate OvalEdge upstream slowness or warm/cold Lambda behavior — correlate `mcp_tool duration_ms` with OvalEdge HTTP logs (`OVALEDGE_LOG_HTTP_REQUESTS=true` in Lambda env).

## Client config (`mcp-remote` + Claude)

```json
{
  "mcpServers": {
    "ovaledge": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://<api-id>.execute-api.<region>.amazonaws.com/mcp",
        "--header",
        "X-OvalEdge-Token:<token>",
        "--header",
        "X-OvalEdge-Secret:<secret>"
      ]
    }
  }
}
```

Rotate tokens if they appeared in shared logs. Never commit secrets to git.

## When to escalate

1. `validate_remote_mcp.py --credentials` fails consistently → OvalEdge auth / URL issue.
2. `/health` shows `mcp_lifespan_ready: false` after warm requests → Lambda lifespan bug; check holder task errors in CloudWatch.
3. `mcp_tool` logs show `outcome=ok` but client still gets 500 → response size or API Gateway payload limit (investigate response trimming / `slim_tool_response`).
4. Only specific tools fail → OvalEdge API for that path; enable `OVALEDGE_LOG_HTTP_REQUESTS` temporarily on Lambda.
