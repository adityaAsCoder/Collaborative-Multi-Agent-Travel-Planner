export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function fetchApi(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        }
    });

    if (!res.ok) {
        let err = "API Error";
        try {
            const data = await res.json();
            err = data.detail || err;
        } catch {
            err = res.statusText;
        }
        throw new Error(err);
    }

    return res.json();
}
