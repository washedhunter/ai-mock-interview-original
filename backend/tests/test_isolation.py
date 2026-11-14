"""Per-user data isolation: another user's interview behaves exactly like a missing one."""

from .conftest import answer, new_interview, signup


def test_other_users_data_is_invisible(client):
    signup(client, "a@example.com")
    iv_a = new_interview(client)
    answer(client, iv_a, 0)
    client.post(f"/api/interviews/{iv_a['id']}/complete")
    client.post("/api/auth/logout")

    signup(client, "b@example.com")
    base = f"/api/interviews/{iv_a['id']}"
    q = iv_a["questions"][1]
    assert client.get("/api/interviews").json() == []
    assert client.get(base).status_code == 404
    assert answer(client, iv_a, 1).status_code == 404
    assert client.post(f"{base}/questions/{q['id']}/answer").status_code in (404, 422)
    assert client.post(f"{base}/complete").status_code == 404
    assert client.delete(base).status_code == 404
    prog = client.get("/api/progress").json()
    assert prog["points"] == [] and prog["by_role"] == []

    # A's data is untouched.
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "a@example.com", "password": "correct horse 1"})
    assert client.get(base).status_code == 200
    assert len(client.get("/api/progress").json()["points"]) == 1
