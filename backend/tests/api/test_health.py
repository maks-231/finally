"""Tests for GET /api/health."""

from __future__ import annotations


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
