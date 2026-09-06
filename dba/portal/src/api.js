// Client API du portail DBA — même convention que tickets/portal/src/api.js.
export const API_BASE_URL =
  import.meta.env.VITE_DBA_API_BASE_URL || "http://localhost:6114";

async function request(path, options = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, options);
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: { error: String(err) } };
  }
}

export const getJson = (path) => request(path);
export const postJson = (path, body) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const putJson = (path, body) =>
  request(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const deleteJson = (path) => request(path, { method: "DELETE" });
export const deleteJsonWithBody = (path, body) =>
  request(path, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
