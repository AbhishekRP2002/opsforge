"""Explicit service content crosses Episode and the native bridge losslessly."""

import json

import pytest
from itops_env.server.core.episode import response

BLOCKS = [
    {"type": "text", "text": "attachment evidence"},
    {"type": "image", "data": "YWJj", "mimeType": "image/png"},
    {"type": "audio", "data": "YWJj", "mimeType": "audio/wav"},
    {"type": "resource_link", "uri": "attachment://one", "name": "one"},
    {
        "type": "resource",
        "resource": {
            "uri": "attachment://one",
            "mimeType": "application/octet-stream",
            "blob": "YXNzZXQgZXZpZGVuY2U=",
        },
    },
]


def test_ordinary_content_key_remains_business_json():
    value = {"content": BLOCKS, "message": "ordinary business data"}
    for provider in (None, "okta", "servicenow", "erpnext"):
        observation = response(value, provider=provider)
        assert observation.content == [
            {
                "type": "text",
                "text": json.dumps(
                    value, indent=2 if provider == "servicenow" else None
                ),
            }
        ]


@pytest.mark.parametrize(
    "block", BLOCKS, ids=["text", "image", "audio", "link", "resource"]
)
def test_explicit_content_preserves_each_supported_block(block):
    from itops_env.server.services import results

    assert hasattr(results, "ServiceContent")
    carrier = results.ServiceContent(content=[block])
    observation = response(carrier, provider="erpnext")
    assert observation.content == [block]
    assert observation.is_error is False


def test_explicit_content_owns_and_validates_blocks():
    from itops_env.server.services import results

    assert hasattr(results, "ServiceContent")
    blocks = [{"type": "text", "text": "original"}]
    carrier = results.ServiceContent.model_validate({"content": blocks})
    blocks[0]["text"] = "changed"
    assert response(carrier).content == [{"type": "text", "text": "original"}]
    with pytest.raises(ValueError):
        results.ServiceContent.model_validate({"content": [{"type": "unknown"}]})
