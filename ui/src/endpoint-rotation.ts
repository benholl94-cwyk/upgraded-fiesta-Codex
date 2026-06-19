export type EndpointState = "unknown" | "online" | "offline" | "degraded" | "zero_staked";

export interface EndpointConfig {
  id: string;
  label: string;
  baseUrl: string;
  healthPath: string;
  taskPath: string;
  priority: number;
}

export interface PlatformConfig {
  platformName: string;
  requestTimeoutMs: number;
  maxAttemptsPerDispatch: number;
  zeroStakedStatus: string;
  endpoints: EndpointConfig[];
}

export interface EndpointHealth {
  endpoint: EndpointConfig;
  state: EndpointState;
  httpStatus?: number;
  latencyMs: number;
  reason: string;
  checkedAt: string;
}

export interface DispatchRequest {
  taskType: string;
  objective: string;
  payload: unknown;
}

export interface DispatchResult {
  endpoint: EndpointConfig;
  ok: boolean;
  httpStatus?: number;
  state: EndpointState;
  response: unknown;
  attempts: EndpointHealth[];
}

const defaultConfig: PlatformConfig = {
  platformName: "Heavy Metal AI Control Plane",
  requestTimeoutMs: 8000,
  maxAttemptsPerDispatch: 3,
  zeroStakedStatus: "zero_staked",
  endpoints: [
    { id: "primary", label: "Primary Gateway", baseUrl: "/api", healthPath: "/health", taskPath: "/tasks", priority: 1 },
    { id: "gateway-fallback", label: "Fallback Gateway", baseUrl: "/gateway", healthPath: "/health", taskPath: "/tasks", priority: 2 }
  ]
};

export async function loadPlatformConfig(): Promise<PlatformConfig> {
  try {
    const response = await fetch("/platform-config.json", { cache: "no-store" });
    if (!response.ok) return defaultConfig;
    const config = (await response.json()) as PlatformConfig;
    if (!Array.isArray(config.endpoints) || config.endpoints.length === 0) return defaultConfig;
    return {
      ...defaultConfig,
      ...config,
      endpoints: [...config.endpoints].sort((a, b) => a.priority - b.priority)
    };
  } catch {
    return defaultConfig;
  }
}

function joinUrl(baseUrl: string, path: string): string {
  const base = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

function detectState(value: unknown, zeroStakedStatus: string): EndpointState {
  if (!value || typeof value !== "object") return "online";
  const source = value as Record<string, unknown>;
  const raw = String(source.status ?? source.state ?? source.health ?? "online").toLowerCase();
  if (raw === zeroStakedStatus || raw === "zero-staked" || raw === "zero staked") return "zero_staked";
  if (raw === "degraded" || raw === "warning") return "degraded";
  if (raw === "offline" || raw === "down" || raw === "failed") return "offline";
  return "online";
}

async function fetchJsonWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<{ status: number; body: unknown }> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    const text = await response.text();
    let body: unknown = null;
    if (text.trim().length > 0) {
      try {
        body = JSON.parse(text);
      } catch {
        body = { raw: text };
      }
    }
    return { status: response.status, body };
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function checkEndpoint(config: PlatformConfig, endpoint: EndpointConfig): Promise<EndpointHealth> {
  const started = performance.now();
  const checkedAt = new Date().toISOString();
  try {
    const result = await fetchJsonWithTimeout(joinUrl(endpoint.baseUrl, endpoint.healthPath), { method: "GET" }, config.requestTimeoutMs);
    const latencyMs = Math.round(performance.now() - started);
    if (result.status < 200 || result.status >= 300) {
      return { endpoint, state: "offline", httpStatus: result.status, latencyMs, reason: "non_2xx_health_response", checkedAt };
    }
    const state = detectState(result.body, config.zeroStakedStatus);
    return { endpoint, state, httpStatus: result.status, latencyMs, reason: state === "online" ? "healthy" : "rotation_required", checkedAt };
  } catch (error) {
    return { endpoint, state: "offline", latencyMs: Math.round(performance.now() - started), reason: error instanceof Error ? error.name : "request_failed", checkedAt };
  }
}

export async function dispatchWithRotation(config: PlatformConfig, request: DispatchRequest): Promise<DispatchResult> {
  const endpoints = [...config.endpoints].sort((a, b) => a.priority - b.priority);
  const attempts: EndpointHealth[] = [];
  const maxAttempts = Math.min(config.maxAttemptsPerDispatch, endpoints.length);

  for (const endpoint of endpoints.slice(0, maxAttempts)) {
    const health = await checkEndpoint(config, endpoint);
    attempts.push(health);
    if (health.state !== "online") continue;

    const result = await fetchJsonWithTimeout(
      joinUrl(endpoint.baseUrl, endpoint.taskPath),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...request, submittedAt: new Date().toISOString() })
      },
      config.requestTimeoutMs
    );
    const state = detectState(result.body, config.zeroStakedStatus);
    if (result.status >= 200 && result.status < 300 && state === "online") {
      return { endpoint, ok: true, httpStatus: result.status, state, response: result.body, attempts };
    }
    attempts.push({ endpoint, state, httpStatus: result.status, latencyMs: 0, reason: "dispatch_response_rotation_required", checkedAt: new Date().toISOString() });
  }

  return { endpoint: endpoints[0], ok: false, state: "offline", response: { error: "no_healthy_endpoint_available" }, attempts };
}
