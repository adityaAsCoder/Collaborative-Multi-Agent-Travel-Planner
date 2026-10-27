export const PUBLIC_PATHS = new Set(["/", "/login", "/register"]);

export function isPublicPath(pathname) {
    return PUBLIC_PATHS.has(pathname);
}

export function loginRedirect(pathname, search = "") {
    const returnTo = `${pathname}${search}`;
    return `/login?returnTo=${encodeURIComponent(returnTo)}`;
}

export function clearClientAuth(storage) {
    storage.removeItem("user_email");
    storage.removeItem("last_itinerary");
}
