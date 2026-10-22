import json

from amazon_audit.synthetic import generate_csv


def upload(client, content=None, business="demo", filename="seller.csv", **kwargs):
    return client.post(
        f"/audits?business_id={business}",
        files={"file": (filename, generate_csv() if content is None else content, "text/csv")},
        **kwargs,
    )


def test_full_workflow_persisted_json_report_and_isolation(client):
    assert client.get("/health").json()["status"] == "ok"
    response = upload(client)
    assert response.status_code == 201, response.text
    run_id = response.json()["run_id"]
    run = client.get(f"/audits/{run_id}").json()
    assert run["status"] == "completed"
    assert run["result"]["summary"]["sku_count"] == 24
    assert run["result"]["summary"]["complete_profitability_skus"] == 23
    assert run["result"]["evaluation"]["passed"]
    assert len(run["tasks"]) == 3
    assert all(t["status"] == "completed" and t["estimated_cost_usd"] == "0.00" for t in run["tasks"])
    assert all(p["status"] == "proposed" for p in run["result"]["improvement_proposals"])
    html = client.get(f"/audits/{run_id}/report")
    assert html.status_code == 200 and "Profit overview" in html.text
    assert "SYN-001" in html.text and "Supporting calculations" in html.text
    assert "default-src 'none'" in html.headers["content-security-policy"]
    other = upload(client, business="another").json()["run_id"]
    assert other != run_id
    assert client.get(f"/audits/{other}").json()["business_id"] == "another"
    assert client.get(f"/audits/{run_id}").json()["business_id"] == "demo"
    json.dumps(run, allow_nan=False)


def test_failed_upload_persists_failure_and_does_not_leak_records(client):
    response = upload(client, b"sku,secret\nPRIVATE,DATA\n")
    assert response.status_code == 422
    assert "PRIVATE" not in response.text
    run_id = response.json()["detail"]["run_id"]
    run = client.get(f"/audits/{run_id}").json()
    assert run["status"] == "failed" and run["tasks"][0]["status"] == "failed"
    assert run["error"] == "InvalidDataset" and run["result"] is None
    assert client.get(f"/audits/{run_id}/report").status_code == 404


def test_file_type_size_and_missing_runs(client):
    assert upload(client, filename="seller.exe").status_code == 415
    assert upload(client, b"x" * 20001).status_code == 413
    assert upload(client, b"x" * 90000).status_code == 413
    assert client.get("/audits/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/audits/not-a-uuid").status_code == 422


def test_resume_requires_same_input_and_business(client):
    run_id = upload(client).json()["run_id"]
    response = client.post(
        f"/audits?business_id=demo&resume={run_id}",
        files={"file": ("seller.csv", generate_csv(), "text/csv")},
    )
    assert response.status_code == 201 and response.json()["run_id"] == run_id
    response = client.post(
        f"/audits?business_id=other&resume={run_id}",
        files={"file": ("seller.csv", generate_csv(), "text/csv")},
    )
    assert response.status_code == 409


def test_report_escapes_untrusted_product_name(client):
    content = generate_csv().replace(b"Synthetic Beard Oil", b"<script>alert(1)</script>")
    run_id = upload(client, content).json()["run_id"]
    html = client.get(f"/audits/{run_id}/report").text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_whole_body_cap_without_content_length(client):
    body = b"x" * 90000
    response = client.post(
        "/audits",
        content=iter([body[:40000], body[40000:]]),
        headers={"Content-Type": "multipart/form-data; boundary=test"},
    )
    assert response.status_code == 413
