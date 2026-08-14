# Environment Variable Audit Report

**Date**: 2026-08-13  
**Auditor**: Antigravity  
**Repository**: `cdbaws` (mcarememory)

---

## Step 1 — Raw Audit Findings

### 1.1 Complete List of Environment Variables Read in Code
Every unique variable name found across `app/`, `scripts/`, `render.yaml`, and `.env`, with exact file and line references:

1. **`AWS_ACCESS_KEY_ID`**
   - Read implicitly by `boto3` SDK in `app/embeddings.py` (L53), `scripts/deploy_embedding_endpoint.py` (L76), `scripts/deploy_serverless_embedding_endpoint.py` (L61), `scripts/teardown_embedding_endpoint.py` (L49)
   - Specified in `render.yaml` (L17), `.env` (L1)

2. **`AWS_SECRET_ACCESS_KEY`**
   - Read implicitly by `boto3` SDK in `app/embeddings.py` (L53), `scripts/deploy_embedding_endpoint.py` (L76), `scripts/deploy_serverless_embedding_endpoint.py` (L61), `scripts/teardown_embedding_endpoint.py` (L49)
   - Specified in `render.yaml` (L19), `.env` (L2)

3. **`AWS_REGION`**
   - Read in `app/config.py` (L14-17)
   - Used via import in `app/embeddings.py` (L7, L53), `scripts/deploy_embedding_endpoint.py` (L18, L39, L65, L76), `scripts/deploy_serverless_embedding_endpoint.py` (L18, L36, L54, L61, L117, L127), `scripts/teardown_embedding_endpoint.py` (L10, L40, L49, L61), `scripts/auto_safety_timer.py` (L15, L42)
   - Specified in `render.yaml` (L15), `.env` (L3)

4. **`AWS_DEFAULT_REGION`**
   - Read as fallback in `app/config.py` (L16)
   - Set dynamically in environment by `scripts/deploy_embedding_endpoint.py` (L39), `scripts/deploy_serverless_embedding_endpoint.py` (L36)

5. **`COCKROACH_URL`**
   - Read in `app/config.py` (L8-11)
   - Used via import in `app/memory_store.py` (L3, L10, L16), `scripts/migrate_to_cloud.py` (L8, L34), `scripts/explain_scale_query.py` (L9)
   - Specified in `.env` (L4)

6. **`COCKROACH_CLOUD_URL`**
   - Read in `app/config.py` (L45), `scripts/migrate_to_cloud.py` (L18), `scripts/verify_cloud_explain.py` (L18)
   - Used via import in `app/memory_store.py` (L10, L11, L12)
   - Specified in `.env` (L9)

7. **`DATABASE_URL`**
   - Specified in `render.yaml` (L11)
   - **NOT read anywhere in application Python code** (0 references)

8. **`SAGEMAKER_ROLE_ARN`**
   - Read in `scripts/deploy_embedding_endpoint.py` (L53), `scripts/deploy_serverless_embedding_endpoint.py` (L41)
   - Specified in `.env` (L5)

9. **`SAGEMAKER_ENDPOINT_NAME`**
   - Read in `app/config.py` (L26), `scripts/deploy_embedding_endpoint.py` (L42), `scripts/deploy_serverless_embedding_endpoint.py` (L39), `scripts/teardown_embedding_endpoint.py` (L25)
   - Specified in `.env` (L6)

10. **`EMBEDDING_MODE`**
    - Read in `app/config.py` (L42), `app/embeddings.py` (L202, L227)
    - Specified in `.env` (L7)

11. **`EMBEDDING_DIMENSION`**
    - Read in `app/config.py` (L41)

12. **`DB_MODE`**
    - Read in `app/config.py` (L46), `app/memory_store.py` (L10, L11, L185, L235)
    - Written dynamically in `scripts/verify_cloud_mcp.py` (L5)
    - Specified in `.env` (L8)

13. **`COCKROACHDB_MCP_API_KEY`**
    - Read in `app/config.py` (L49), `app/mcp_client.py` (L16, L26, L33)
    - Specified in `.env` (L10)

14. **`COCKROACHDB_CLUSTER_ID`**
    - Read in `app/config.py` (L50), `app/mcp_client.py` (L18)

15. **`COCKROACHDB_MCP_URL`**
    - Read in `app/config.py` (L51), `app/mcp_client.py` (L17)

16. **`ANTHROPIC_API_KEY`**
    - Read in `app/config.py` (L54), `app/coordinator_agent.py` (L4, L78, L133)
    - Specified in `render.yaml` (L13), `.env` (L11)

17. **`ANTHROPIC_MODEL`**
    - Read in `app/config.py` (L55), `app/coordinator_agent.py` (L4, L135)
    - Specified in `.env` (L12)

18. **`ACTIVE_CONVERSATION_ID`**
    - Read in `app/config.py` (L59)
    - Specified in `render.yaml` (L21)

19. **`SAFETY_TIMER_MINUTES`**
    - Read in `scripts/deploy_embedding_endpoint.py` (L44), `scripts/auto_safety_timer.py` (L24)

---

### 1.2 Variable Names Present in Local `.env` File
Every line in `.env`:
1. `AWS_ACCESS_KEY_ID`
2. `AWS_SECRET_ACCESS_KEY`
3. `AWS_REGION`
4. `COCKROACH_URL`
5. `SAGEMAKER_ROLE_ARN`
6. `SAGEMAKER_ENDPOINT_NAME`
7. `EMBEDDING_MODE`
8. `DB_MODE`
9. `COCKROACH_CLOUD_URL`
10. `COCKROACHDB_MCP_API_KEY`
11. `ANTHROPIC_API_KEY`
12. `ANTHROPIC_MODEL`

---

## Step 2 — Analysis of Duplicates and Dead Variables

1. **`COCKROACH_URL` vs. `COCKROACH_CLOUD_URL`**:
   - **Finding**: They are **two distinct target databases** with different connection strings for two different environments.
   - **Evidence**:
     - `COCKROACH_URL` (`postgresql://root@localhost:26257/agent_memory?sslmode=disable`) connects to the **local Docker CockroachDB cluster**. Used when `DB_MODE=local` (`app/memory_store.py` L16) and by local scripts (`explain_scale_query.py` L9).
     - `COCKROACH_CLOUD_URL` (`postgresql://xrezzy:...@cdbaws-31819.j77.aws-ap-south-1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full`) connects to **CockroachDB Cloud Serverless**. Used when `DB_MODE=cloud` or `DB_MODE=cloud-mcp` (`app/memory_store.py` L11-15).

2. **`COCKROACHDB_MCP_API_KEY`**:
   - **Finding**: **Actively read and used** by `mcp_client.py`.
   - **Evidence**: `app/mcp_client.py` imports `COCKROACHDB_MCP_API_KEY` from `app.config` (L6), validates it (L27), and passes it in the `Authorization: Bearer <key>` header (L33) for HTTP JSON-RPC calls to `https://cockroachlabs.cloud/mcp`.

3. **`ANTHROPIC_MODEL`**:
   - **Finding**: **Actively read and used** by `coordinator_agent.py`.
   - **Evidence**: `app/coordinator_agent.py` imports `ANTHROPIC_MODEL` (L4) and passes `model=ANTHROPIC_MODEL` to `client.messages.create(...)` (L135).

4. **`EMBEDDING_MODE=sagemaker`**:
   - **Finding**: **Actively read and used** by `embeddings.py`.
   - **Evidence**: `app/embeddings.py` checks `mode = os.getenv("EMBEDDING_MODE", EMBEDDING_MODE).lower().strip()` at L202 and L227 to decide between `_generate_embedding_sagemaker` and `_generate_embedding_local`.

5. **Other dead/unused variables in `.env`**:
   - **Finding**: None. All 12 variables in `.env` are actively read by code or SDKs.

6. **`DATABASE_URL`**:
   - **Finding**: Confirmed **NOT read anywhere in code**.
   - **Evidence**: Listed in `render.yaml` (L11), but `app/config.py` and `app/memory_store.py` read `COCKROACH_CLOUD_URL` for cloud database connections.
   - **Mapping**: `DATABASE_URL` in `render.yaml` maps directly to `COCKROACH_CLOUD_URL`.
