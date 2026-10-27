import test from "node:test";
import assert from "node:assert/strict";
import {
    clearClientAuth,
    isPublicPath,
    loginRedirect,
} from "./auth.js";

test("401 policy only treats public routes as redirect-safe", () => {
    assert.equal(isPublicPath("/login"), true);
    assert.equal(isPublicPath("/plan"), false);
    assert.equal(loginRedirect("/plan", "?draft=1"), "/login?returnTo=%2Fplan%3Fdraft%3D1");
});

test("centralized auth cleanup removes identity and cached itinerary", () => {
    const removed = [];
    clearClientAuth({ removeItem: (key) => removed.push(key) });
    assert.deepEqual(removed, ["user_email", "last_itinerary"]);
});
