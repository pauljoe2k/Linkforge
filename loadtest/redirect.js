// k6 load test for the redirect endpoint (same methodology as locustfile.py).
//   linkforge-slug=loadtest k6 run loadtest/redirect.js
export const options = {
  scenarios: {
    redirects: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "5s", target: 50 }, // ramp up
        { duration: "20s", target: 50 }, // steady state — this is the window to read
        { duration: "5s", target: 0 },
      ],
    },
  },
};

const SLUG = __ENV.LINKFORGE_SLUG || "loadtest";
const BASE = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const res = http.get(`${BASE}/${SLUG}`, { redirects: 0 });
  check(res, { "status 302": (r) => r.status === 302 });
}
