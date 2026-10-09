"""Exercise the isolated Docker CRM through its real HTTP proxy and login."""

import time

import requests

BASE = "http://127.0.0.1:3088/api"


def main():
    products = []
    requests.get(f"{BASE}/health/ready", timeout=10).raise_for_status()
    for tenant in (1, 2):
        with requests.Session() as http:
            response = http.post(
                f"{BASE}/auth/login",
                json={
                    "email": f"demo{tenant}@example.com",
                    "password": "DockerTeste@2026",
                },
                timeout=15,
            )
            response.raise_for_status()
            http.get(f"{BASE}/auth/me", timeout=10).raise_for_status()
            http.headers["Authorization"] = "Bearer " + response.json()["access_token"]
            response = http.post(
                f"{BASE}/crm/market-intelligence/sync",
                json={"source": "crm"},
                timeout=10,
            )
            assert response.status_code == 202
            run_id = response.json()["id"]
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                response = http.get(
                    f"{BASE}/crm/market-intelligence/sync-runs", timeout=10
                )
                response.raise_for_status()
                run = next(row for row in response.json() if row["id"] == run_id)
                assert run["status"] != "failed", "CRM worker job failed"
                if run["status"] == "completed":
                    break
                time.sleep(1)
            else:
                raise AssertionError("Timed out waiting for CRM worker")
            response = http.get(
                f"{BASE}/crm/market-intelligence/facts?kind=demand", timeout=10
            )
            response.raise_for_status()
            rows = response.json()["rows"]
            assert len(rows) == 1 and rows[0]["tenant_id"] == tenant
            assert float(rows[0]["total_value"]) == 6500 * tenant
            for path in (
                "report",
                "diagnostic",
                "operations",
                "export?section=assortment",
            ):
                http.get(
                    f"{BASE}/crm/market-intelligence/{path}", timeout=10
                ).raise_for_status()
            result = http.get(
                f"{BASE}/crm/market-intelligence/report", timeout=10
            ).json()
            products.append(
                {
                    row["product_id"]
                    for row in result["product_demand"]
                    if row["product_id"]
                }
            )
            assert len(products[-1]) == 1
            assert (
                http.get(
                    f"{BASE}/crm/market-intelligence/capabilities", timeout=10
                ).json()["sources"]["bling"]
                == "planned"
            )
        print(
            f"Tenant {tenant}: real login, queued CRM job, isolated facts, report and CSV passed."
        )
    assert products[0].isdisjoint(products[1]), (
        "Product explorer leaked between tenants"
    )
    print(
        "Docker integration and product explorer isolation passed through the frontend proxy."
    )


if __name__ == "__main__":
    main()
