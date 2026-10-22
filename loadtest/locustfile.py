"""Locust load test for the redirect endpoint.

Run against a LINK already in the database (or a seeded one via
loadtest/seed.py):

    linkforge-slug=loadtest locust -f loadtest/locustfile.py \
        --headless -u 50 -r 10 --run-time 30s --host http://localhost:8000

How to read the output:
- "Req/s" in the stats table is throughput actually completed per second —
  the number to quote from load tests.
- "P95" on the /[slug] row: 95% of redirects completed faster than this.
  Locust reports ms percentiles; anything > ~50ms locally means the server
  is saturated, not the network.
- Steady state: RPS flat for the middle of the run (ignore ramp-up tail),
  failures 0. Rising P95 with flat RPS = queued capacity, not more work.
"""

import os

from locust import HttpUser, between, task

SLUG = os.environ.get("LINKFORGE_SLUG", "loadtest")


class RedirectVisitor(HttpUser):
    # Real visitors arrive without token/auth; only GET /{slug}.
    wait_time = between(0.0, 0.05)

    @task
    def redirect(self):
        # name="//" buckets the dynamic path under one stats row
        self.client.get(f"/{SLUG}", name="/[slug]", allow_redirects=False)
