import base64
import json

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import load_scenario
from itops_env.server.itops_environment import ItopsEnvironment


@pytest.fixture
def env():
    world = ItopsEnvironment(
        scenario=load_scenario().model_copy(
            update={"step_budget": 1000, "horizon": 5000}
        )
    )
    world.reset()
    yield world
    world.close()


def call(env, tool, **arguments):
    observation = env.step(
        ItopsAction(
            provider="erpnext", tool_name="erpnext_" + tool, arguments=arguments
        )
    )
    return json.loads(observation.content[0]["text"]), observation.is_error


def create(env, doctype, **data):
    value, error = call(env, "doc_create", doctype=doctype, data=data)
    assert not error, value
    return value["data"]


def test_generic_documents_share_updates_filters_and_nonreused_identity(env):
    first = create(
        env,
        "Company",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    name = first["name"]
    updated, error = call(
        env, "doc_update", doctype="Company", name=name, data={"domain": "Services"}
    )
    assert not error and updated["data"]["domain"] == "Services"
    assert updated["data"]["modified"] > first["modified"]
    listed, error = call(
        env,
        "doc_list",
        doctype="Company",
        fields=["name", "domain"],
        filters=[["domain", "=", "Services"]],
    )
    assert not error and listed["data"] == [{"name": name, "domain": "Services"}]
    assert (
        call(env, "doc_get", doctype="Company", name=name)[0]["data"]["domain"]
        == "Services"
    )
    assert call(env, "doc_delete", doctype="Company", name=name)[0]["deleted"] is True
    second = create(
        env,
        "Company",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    assert second["name"] != name


@pytest.mark.parametrize(
    "tool,args",
    [
        ("doc_create", {"doctype": "Unknown", "data": {}}),
        (
            "doc_update",
            {"doctype": "Company", "name": "missing", "data": {"domain": "x"}},
        ),
        ("doc_get", {"doctype": "Company", "name": "missing"}),
        ("doc_delete", {"doctype": "Company", "name": "missing"}),
        ("doc_list", {"doctype": "Company", "filters": [["name", "SQL", "x"]]}),
        ("doc_list", {"doctype": "Company", "order_by": "count(*) desc"}),
        ("doc_list", {"doctype": "Company", "limit": 1.5}),
        ("method_call", {"method": "os.system", "args": {"command": "bad"}}),
    ],
)
def test_operations_deliberate_errors(env, tool, args):
    value, error = call(env, tool, **args)
    assert error and value["error"]
    assert env.state.phase == "active"


def test_nested_values_and_identity_updates_are_rejected_without_mutation(env):
    doc = create(
        env,
        "Company",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    for data in (
        {"company_name": []},
        {"name": "forged"},
        {"docstatus": 1},
        {"modified": "forged"},
    ):
        assert call(env, "doc_update", doctype="Company", name=doc["name"], data=data)[
            1
        ]
    assert call(env, "doc_get", doctype="Company", name=doc["name"])[0]["data"] == doc


def test_file_bytes_parent_privacy_replay_and_generic_bypass(env):
    parent = create(
        env,
        "Company",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    arguments = {
        "file_name": "evidence.txt",
        "content_base64": "YXNzZXQgZXZpZGVuY2U=",
        "attached_to_doctype": "Company",
        "attached_to_name": parent["name"],
    }
    action = ItopsAction(
        provider="erpnext",
        tool_name="erpnext_file_upload",
        arguments=arguments,
        invocation_id="upload",
    )
    uploaded = env.step(action)
    assert not uploaded.is_error
    file = json.loads(uploaded.content[0]["text"])["data"]
    assert file["file_size"] == 14 and file["is_private"] == 1
    assert env.step(action).content == uploaded.content
    assert env.state.step_count == 2
    listed, error = call(
        env, "file_list", attached_to_doctype="Company", attached_to_name=parent["name"]
    )
    assert (
        not error and listed["count"] == 1 and listed["data"][0]["is_private"] is True
    )
    downloaded = env.step(
        ItopsAction(
            provider="erpnext",
            tool_name="erpnext_file_download",
            arguments={
                "file_id": file["name"],
                "attached_to_doctype": "Company",
                "attached_to_name": parent["name"],
            },
        )
    )
    assert not downloaded.is_error
    assert (
        downloaded.content[0]["text"]
        == "Prepared evidence.txt for download (14 bytes)."
    )
    assert (
        base64.b64decode(downloaded.content[1]["resource"]["blob"]) == b"asset evidence"
    )
    assert env.state.step_count == 4 and env.state.simulated_clock == 4
    assert call(
        env,
        "file_download",
        file_id=file["name"],
        attached_to_doctype="Company",
        attached_to_name="other",
    )[1]
    assert call(
        env,
        "doc_update",
        doctype="File",
        name=file["name"],
        data={"file_url": "artifacts/other"},
    )[1]
    assert call(env, "doc_create", doctype="File", data=file)[1]


@pytest.mark.parametrize(
    "changes",
    [
        {"file_name": "../bad"},
        {"file_name": "bad\\path"},
        {"content_base64": "bad!"},
        {"content_base64": "A"},
        {"attached_to_name": "missing"},
    ],
)
def test_file_invalid_inputs_do_not_store_bytes(env, changes):
    parent = create(
        env,
        "Company",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    args = {
        "file_name": "safe",
        "content_base64": "YWJj",
        "attached_to_doctype": "Company",
        "attached_to_name": parent["name"],
    } | changes
    assert call(env, "file_upload", **args)[1]
    assert (
        call(
            env,
            "file_list",
            attached_to_doctype="Company",
            attached_to_name=parent["name"],
        )[0]["count"]
        == 0
    )


def test_setup_and_allowed_method_read_mutated_state(env):
    company, error = call(
        env,
        "company_create",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    assert not error
    assert call(env, "company_list")[0]["data"][0]["name"] == company["data"]["name"]
    user = create(
        env,
        "User",
        name="alice@example.test",
        full_name="Alice",
        enabled=1,
        user_type="System User",
    )
    create(
        env,
        "User",
        name="disabled@example.test",
        full_name="Disabled",
        enabled=0,
        user_type="System User",
    )
    assert call(env, "user_list", search="Ali")[0]["data"] == [
        {"name": user["name"], "full_name": "Alice", "enabled": 1}
    ]
    assert call(
        env,
        "method_call",
        method="frappe.client.get_count",
        args={"doctype": "User"},
        http_method="GET",
    )[0] == {"data": 2}
    for tool, args in (
        (
            "company_create",
            {
                "company_name": "",
                "abbr": "AC",
                "default_currency": "USD",
                "country": "US",
            },
        ),
        ("company_list", {"limit": -1}),
        ("user_list", {"limit": -1}),
    ):
        assert call(env, tool, **args)[1]
