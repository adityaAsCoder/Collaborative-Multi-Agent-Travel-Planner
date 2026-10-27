export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
import { clearClientAuth, isPublicPath, loginRedirect } from "./auth";
let redirectingForAuth = false;

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}

function redirectToLogin() {
    if (typeof window === "undefined" || redirectingForAuth || isPublicPath(window.location.pathname)) {
        return;
    }
    redirectingForAuth = true;
    clearClientAuth({
        removeItem: (key) => {
            localStorage.removeItem(key);
            if (key === "last_itinerary") sessionStorage.removeItem(key);
        },
    });
    window.location.assign(loginRedirect(window.location.pathname, window.location.search));
}

function readCookie(name) {
    if (typeof document === "undefined") return "";
    const prefix = `${name}=`;
    return document.cookie.split("; ").find((cookie) => cookie.startsWith(prefix))?.slice(prefix.length) || "";
}

async function ensureCsrfToken() {
    const existing = readCookie("wanderwise_csrf");
    if (existing) return existing;
    const response = await fetch(`${API_BASE}/auth/csrf`, { credentials: "include" });
    if (!response.ok) throw new ApiError("Unable to initialize request protection.", response.status);
    const data = await response.json();
    return data.csrf_token;
}

export async function fetchApi(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const method = (options.method || "GET").toUpperCase();
    const headers = { "Content-Type": "application/json", ...options.headers };
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
        headers["X-CSRF-Token"] = await ensureCsrfToken();
    }
    const res = await fetch(url, {
        ...options,
        credentials: 'include',
        headers,
    });

    if (!res.ok) {
        let err = "API Error";
        try {
            const data = await res.json();
            err = data.detail || err;
        } catch {
            err = res.statusText;
        }
        if (res.status === 401) redirectToLogin();
        throw new ApiError(err, res.status);
    }

    return res.json();
}

export async function logout() {
    return fetchApi('/auth/logout', { method: 'POST' });
}

export { ApiError, isPublicPath };
