const endpoints = [
  { id: 'primary', label: 'Primary API', baseUrl: '/api', healthPath: '/health', taskPath: '/tasks' },
  { id: 'gateway', label: 'Gateway API', baseUrl: '/gateway', healthPath: '/health', taskPath: '/tasks' },
  { id: 'local', label: 'Local API', baseUrl: 'http://127.0.0.1:8080', healthPath: '/health', taskPath: '/tasks' }
];

let activeIndex = 0;
const state = {
  lastResult: 'idle',
  lastEndpoint: endpoints[activeIndex].id,
  history: []
};

function joinUrl(baseUrl, path) {
  return `${baseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
}

function isZeroStaked(payload) {
  const text = JSON.stringify(payload || {}).toLowerCase();
  return text.includes('zero_staked') || text.includes('zero-staked') || text.includes('zero staked');
}

async function requestJson(url, options = {}, timeoutMs = 6000) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const text = await response.text();
    let payload = {};
    if (text) {
      try { payload = JSON.parse(text); } catch { payload = { raw: text }; }
    }
    return { ok: response.ok, status: response.status, payload };
  } finally {
    window.clearTimeout(timeout);
  }
}

function rotateEndpoint(reason) {
  activeIndex = (activeIndex + 1) % endpoints.length;
  state.lastEndpoint = endpoints[activeIndex].id;
  state.history.unshift(`${new Date().toISOString()} rotate: ${reason} -> ${state.lastEndpoint}`);
  render();
}

async function checkActiveEndpoint() {
  const endpoint = endpoints[activeIndex];
  const url = joinUrl(endpoint.baseUrl, endpoint.healthPath);
  try {
    const result = await requestJson(url, { method: 'GET', headers: { Accept: 'application/json' } });
    if (!result.ok || isZeroStaked(result.payload)) {
      state.lastResult = `unavailable ${endpoint.id}`;
      rotateEndpoint('health unavailable or zero_staked');
      return false;
    }
    state.lastResult = `online ${endpoint.id}`;
    state.history.unshift(`${new Date().toISOString()} health ok: ${endpoint.id}`);
    render();
    return true;
  } catch (error) {
    state.lastResult = `offline ${endpoint.id}`;
    rotateEndpoint(error instanceof Error ? error.message : 'request failed');
    return false;
  }
}

async function submitTask() {
  const objective = document.querySelector('#objective').value.trim();
  const payloadText = document.querySelector('#payload').value.trim() || '{}';
  let payload;
  try {
    payload = JSON.parse(payloadText);
  } catch {
    state.lastResult = 'invalid JSON payload';
    render();
    return;
  }
  for (let attempt = 0; attempt < endpoints.length; attempt += 1) {
    const endpoint = endpoints[activeIndex];
    const url = joinUrl(endpoint.baseUrl, endpoint.taskPath);
    try {
      const result = await requestJson(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ objective, payload, client: 'heavy-metal-ui', createdAt: new Date().toISOString() })
      }, 12000);
      if (result.ok && !isZeroStaked(result.payload)) {
        state.lastResult = `accepted by ${endpoint.id}`;
        state.history.unshift(`${new Date().toISOString()} task accepted: ${endpoint.id}`);
        render();
        return;
      }
      rotateEndpoint('task rejected or zero_staked');
    } catch (error) {
      rotateEndpoint(error instanceof Error ? error.message : 'task request failed');
    }
  }
  state.lastResult = 'all endpoints unavailable';
  render();
}

function render() {
  document.querySelector('#active-endpoint').textContent = endpoints[activeIndex].label;
  document.querySelector('#status').textContent = state.lastResult;
  document.querySelector('#history').innerHTML = state.history.slice(0, 12).map((item) => `<li>${item}</li>`).join('');
}

window.addEventListener('DOMContentLoaded', () => {
  document.querySelector('#check').addEventListener('click', checkActiveEndpoint);
  document.querySelector('#rotate').addEventListener('click', () => rotateEndpoint('manual'));
  document.querySelector('#submit').addEventListener('click', submitTask);
  render();
});
