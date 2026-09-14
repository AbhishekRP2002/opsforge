"""Official MCP SDK preserves raw JSON wrappers and shared Episode accounting."""

import asyncio
import base64
import json
from copy import deepcopy

import httpx
from itops_env import ItopsAction, ItopsEnv
from itops_env.server.itops_environment import ItopsEnvironment
from mcp.types import TextContent
from test_mcp_episode import TOKEN, configuration, native
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def test_native_darwinbox_json_documents_and_exact_direct_parity(live_server):
    url, _ = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset(episode_id="darwinbox-native")
            config = await configuration(control)
            async with native(config, "darwinbox") as (client, _, _):
                discovered = (await client.list_tools()).tools
                assert len(discovered) == 23
                assert (await owner.state()).step_count == 0
                calls = [
                    (
                        "add_employee",
                        {"employees": {"employee_no": "E1", "employee_name": "Ada"}},
                    ),
                    (
                        "upload_profile_attachments",
                        {
                            "employee_no": "E1",
                            "section": "personal",
                            "section_attribute": "proof",
                            "attachment": "ZXZpZGVuY2U=",
                        },
                    ),
                    ("download_personal_docs", {"employee_no": "E1", "for": "proof"}),
                    (
                        "get_employee_details",
                        {"employee_ids": ["E1"], "last_modified": "ignored"},
                    ),
                    ("get_leave_balance", {"employee_nos": ["E1"]}),
                    ("get_employee_details", {}),
                    (
                        "get_employee_history",
                        {
                            "from": "01-01-2026",
                            "to": "31-01-2026",
                            "filter_on_effective_date": 0,
                        },
                    ),
                    (
                        "get_forms_data",
                        {
                            "form_id": "F1",
                            "type": "review",
                            "form_type": "annual",
                            "from": "01-01-2026",
                            "to": "31-01-2026",
                        },
                    ),
                    (
                        "record_attendance_punches",
                        {
                            "attendance": {
                                "E1": [
                                    {
                                        "id": "P1",
                                        "timestamp": "2026-01-04 09:00:00",
                                        "machineid": "M1",
                                        "status": "in",
                                        "location": {"labels": ["office"]},
                                    }
                                ]
                            }
                        },
                    ),
                ]
                raw_calls = deepcopy(calls)
                native_results = []
                for index, (name, arguments) in enumerate(calls, 1):
                    result = await client.call_tool(name, arguments)
                    assert not result.isError and isinstance(
                        result.content[0], TextContent
                    )
                    native_results.append(result)
                    assert (await owner.state()).step_count == index
                    assert (await owner.state()).simulated_clock == index
                doc = json.loads(native_results[2].content[0].text)["data"][0]
                assert base64.b64decode(doc["content_base64"]) == b"evidence"
                assert (
                    json.loads(native_results[3].content[0].text)["data"][0][
                        "employee_no"
                    ]
                    == "E1"
                )
                assert json.loads(native_results[4].content[0].text)["data"] == []
                assert (
                    json.loads(native_results[5].content[0].text)["data"][0][
                        "employee_no"
                    ]
                    == "E1"
                )
                assert json.loads(native_results[7].content[0].text)["data"] == []
                assert json.loads(native_results[8].content[0].text)["data"][0][
                    "location"
                ] == {"labels": ["office"]}
                assert calls == raw_calls
                read = await control.get("/control/artifacts/" + doc["artifact_path"])
                assert read.status_code == 200 and read.content == b"evidence"
                async with httpx.AsyncClient(base_url=url) as outsider:
                    assert (
                        await outsider.get("/control/artifacts/" + doc["artifact_path"])
                    ).status_code == 401
                invalid_calls = [
                    (
                        "record_backdated_attendance",
                        {"attendance": {"attendance_data": [{"employee_no": []}]}},
                    ),
                    ("get_employee_details", {"employee_ids": None}),
                    (
                        "get_employee_history",
                        {
                            "from_": "01-01-2026",
                            "to": "31-01-2026",
                            "filter_on_effective_date": 0,
                        },
                    ),
                    ("record_attendance_punches", {"attendance": {"E1": [{"id": 7}]}}),
                ]
                invalid_results = []
                for name, arguments in invalid_calls:
                    invalid = await client.call_tool(name, arguments)
                    assert invalid.isError
                    invalid_results.append(invalid)
                assert (await owner.state()).step_count == 13 and (
                    await owner.state()
                ).simulated_clock == 13
            await owner.reset(episode_id="darwinbox-reset")
            assert (
                await control.get("/control/artifacts/" + doc["artifact_path"])
            ).status_code == 404
        direct = ItopsEnvironment()
        direct.reset()
        try:
            for index, (name, arguments) in enumerate(calls):
                observed = direct.step(
                    ItopsAction(
                        provider="darwinbox", tool_name=name, arguments=arguments
                    )
                )
                assert observed.content == [
                    block.model_dump(mode="json", exclude_none=True, by_alias=True)
                    for block in native_results[index].content
                ]
            assert direct.state.step_count == 9 and direct.state.simulated_clock == 9
            assert calls == raw_calls
            for index, (name, arguments) in enumerate(invalid_calls):
                observed = direct.step(
                    ItopsAction(
                        provider="darwinbox", tool_name=name, arguments=arguments
                    )
                )
                assert observed.is_error
                assert observed.content == [
                    block.model_dump(mode="json", exclude_none=True, by_alias=True)
                    for block in invalid_results[index].content
                ]
            assert direct.state.step_count == 13 and direct.state.simulated_clock == 13
        finally:
            direct.close()

    asyncio.run(check())
