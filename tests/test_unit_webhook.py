import hmac
import hashlib
import json
import os
import pytest
from starlette.requests import Request
from app.routes.payments import verify_webhook_signature

SECRET = "test-webhook-secret"


def make_request(headers=None, query_string=""):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/payments/webhook",
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in (headers or {}).items()
        ],
        "query_string": query_string.encode(),
    }
    return Request(scope)


def build_signature(secret: str, data_id: str, request_id: str, ts: str) -> str:
    manifest_parts = []
    if data_id:
        manifest_parts.append(f"id:{data_id}")
    if request_id:
        manifest_parts.append(f"request-id:{request_id}")
    manifest_parts.append(f"ts:{ts}")
    message = ";".join(manifest_parts) + ";"
    v1 = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def test_valid_signature_passes():
    signature = build_signature(SECRET, "1234567890", "abc-def", "1700000000")
    request = make_request(
        headers={"x-signature": signature, "x-request-id": "abc-def"},
        query_string="data.id=1234567890",
    )
    assert verify_webhook_signature(request, SECRET) is True


def test_alphanumeric_data_id_included_as_received():
    # El SDK oficial de Python incluye data.id exactamente como llega (sin lowercase)
    signature = build_signature(SECRET, "ABC123XYZ", "req-1", "1700000000")
    request = make_request(
        headers={"x-signature": signature, "x-request-id": "req-1"},
        query_string="data.id=ABC123XYZ",
    )
    assert verify_webhook_signature(request, SECRET) is True


def test_tampered_signature_fails():
    signature = build_signature("wrong-secret", "1234567890", "abc-def", "1700000000")
    request = make_request(
        headers={"x-signature": signature, "x-request-id": "abc-def"},
        query_string="data.id=1234567890",
    )
    assert verify_webhook_signature(request, SECRET) is False


def test_missing_header_fails():
    request = make_request(
        headers={"x-request-id": "abc-def"},
        query_string="data.id=1234567890",
    )
    assert verify_webhook_signature(request, SECRET) is False


def test_missing_data_id_uses_manifest_sin_id():
    # Segun spec de MP, si no viene data.id se omite el campo en el manifiesto
    signature = build_signature(SECRET, "", "abc-def", "1700000000")
    request = make_request(
        headers={"x-signature": signature, "x-request-id": "abc-def"},
        query_string="",
    )
    assert verify_webhook_signature(request, SECRET) is True


def test_ipn_style_id_query_param_passes():
    # IPN legacy envia id=...&topic=payment (sin data.id)
    signature = build_signature(SECRET, "172134263082", "ipn-1", "1700000000")
    request = make_request(
        headers={"x-signature": signature, "x-request-id": "ipn-1"},
        query_string="id=172134263082&topic=payment",
    )
    assert verify_webhook_signature(request, SECRET) is True


def test_empty_secret_fails():
    signature = build_signature(SECRET, "1234567890", "abc-def", "1700000000")
    request = make_request(
        headers={"x-signature": signature, "x-request-id": "abc-def"},
        query_string="data.id=1234567890",
    )
    assert verify_webhook_signature(request, "") is False


def test_malformed_signature_fails():
    request = make_request(
        headers={"x-signature": "not-a-valid-format", "x-request-id": "abc-def"},
        query_string="data.id=1234567890",
    )
    assert verify_webhook_signature(request, SECRET) is False


def test_municipality_centroids_are_valid():
    centroids_path = os.path.join(
        os.path.dirname(__file__), "..", "app", "data", "municipality_centroids.json"
    )
    with open(centroids_path) as f:
        centroids = json.load(f)

    assert centroids, "El archivo de centroides no debe estar vacio"
    for state, municipalities in centroids.items():
        assert isinstance(municipalities, dict), f"Estado '{state}' debe mapear a municipios"
        for name, coords in municipalities.items():
            assert len(coords) == 2, f"'{name}' debe tener [lat, lng]"
            lat, lng = coords
            assert -90 <= lat <= 90, f"Latitud invalida para '{name}': {lat}"
            assert -180 <= lng <= 180, f"Longitud invalida para '{name}': {lng}"


@pytest.mark.skip(reason="Requeriria API key de Gemini; se ejecuta manualmente")
def test_rag_scenarios_placeholder():
    pass
