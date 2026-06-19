# Production API Contract

## Service

`hm-gateway` exposes the production task control API used by the UI control plane.

## Runtime environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `HM_GATEWAY_BIND` | `0.0.0.0:8080` | TCP bind address |
| `HM_ZERO_STAKED` | `false` | Forces health and task responses into `zero_staked` failover status when true |

## Health endpoints

```http
GET /health
GET /api/health
GET /gateway/health
```

Successful online response:

```json
{
  "service": "hm-gateway",
  "status": "online",
  "zero_staked": false,
  "agent_managed": true,
  "task_count": 0,
  "uptime_seconds": 1,
  "checked_at_unix": 0
}
```

Failover response when `HM_ZERO_STAKED=true`:

```json
{
  "service": "hm-gateway",
  "status": "zero_staked",
  "zero_staked": true,
  "agent_managed": true
}
```

## Task dispatch endpoints

```http
POST /tasks
POST /api/tasks
POST /gateway/tasks
```

Request:

```json
{
  "taskType": "analyze",
  "objective": "Validate production readiness",
  "payload": {}
}
```

Accepted response:

```json
{
  "status": "online",
  "accepted": true,
  "task_id": "task-...",
  "task_type": "analyze",
  "agent_managed": true
}
```

When the gateway is in zero-staked mode, task dispatch returns HTTP 503 with status `zero_staked`; the UI rotates to the next configured endpoint.

## Task registry endpoint

```http
GET /tasks
GET /api/tasks
GET /gateway/tasks
```

Returns the in-memory task registry for the current gateway process.

## Operational guarantees

- no client-side secrets;
- fixed endpoint list from `ui/public/platform-config.json`;
- timeout-based endpoint checks;
- zero_staked failover;
- CORS support for configured frontend use;
- no hidden remote command execution.
