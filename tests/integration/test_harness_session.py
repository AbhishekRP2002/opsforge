"""ResourceSession runs real controller-owned episodes for OpenEnv harnesses."""

import importlib
import importlib.util
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from openenv.core.harness import ResourceSession, ResourceSessionFactory
from test_mcp_episode import TOKEN
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture

if TYPE_CHECKING:
    from itops_env.harness import ItopsSessionFactory


def factory(url, **kwargs) -> "ItopsSessionFactory":
    assert importlib.util.find_spec("itops_env.harness") is not None, (
        "Provide the OpenEnv harness integration"
    )
    module = importlib.import_module("itops_env.harness")
    return module.ItopsSessionFactory(url, controller_token=TOKEN, **kwargs)


def complete(session):
    outputs = [
        session.call_tool("okta__get_user", {"user_id": "alex.chen@example.test"}),
        session.call_tool("servicenow__get_user", {"email": "alex.chen@example.test"}),
        session.call_tool(
            "servicenow__add_group_members",
            {"group_id": "a" * 32, "members": ["alex.chen"]},
        ),
        session.call_tool(
            "benchmark__workflow_submit",
            {"disposition": "completed", "user_id": "1" * 32, "group_id": "a" * 32},
        ),
    ]
    assert [output.metadata["reward"] for output in outputs] == [0, 0, 0, 1]
    assert [output.done for output in outputs] == [False, False, False, True]


def test_resource_session_success_and_canonical_verification(live_server):
    url, app = live_server
    sessions = factory(url)
    assert isinstance(sessions, ResourceSessionFactory)
    session = sessions.create(task=None, seed=7, episode_id="harness-success")
    assert isinstance(session, ResourceSession)
    try:
        assert {tool.name for tool in session.list_tools()} == {
            "okta__list_applications",
            "okta__get_application",
            "okta__create_application",
            "okta__update_application",
            "okta__delete_application",
            "okta__confirm_delete_application",
            "okta__activate_application",
            "okta__deactivate_application",
            "okta__list_catalog_apps",
            "okta__get_catalog_app",
            "okta__install_oin_app",
            "okta__list_brands",
            "okta__get_brand",
            "okta__create_brand",
            "okta__replace_brand",
            "okta__delete_brand",
            "okta__list_brand_domains",
            "okta__list_custom_domains",
            "okta__create_custom_domain",
            "okta__get_custom_domain",
            "okta__replace_custom_domain",
            "okta__delete_custom_domain",
            "okta__upsert_custom_domain_certificate",
            "okta__verify_custom_domain",
            "okta__get_error_page_resources",
            "okta__get_customized_error_page",
            "okta__replace_customized_error_page",
            "okta__delete_customized_error_page",
            "okta__get_default_error_page",
            "okta__get_preview_error_page",
            "okta__replace_preview_error_page",
            "okta__delete_preview_error_page",
            "okta__get_sign_in_page_resources",
            "okta__get_customized_sign_in_page",
            "okta__replace_customized_sign_in_page",
            "okta__delete_customized_sign_in_page",
            "okta__get_default_sign_in_page",
            "okta__get_preview_sign_in_page",
            "okta__replace_preview_sign_in_page",
            "okta__delete_preview_sign_in_page",
            "okta__list_sign_in_widget_versions",
            "okta__get_sign_out_page_settings",
            "okta__replace_sign_out_page_settings",
            "okta__list_email_templates",
            "okta__get_email_template",
            "okta__list_email_customizations",
            "okta__create_email_customization",
            "okta__get_email_customization",
            "okta__replace_email_customization",
            "okta__delete_email_customization",
            "okta__delete_all_email_customizations",
            "okta__get_email_customization_preview",
            "okta__get_email_default_content",
            "okta__get_email_default_content_preview",
            "okta__get_email_settings",
            "okta__replace_email_settings",
            "okta__send_test_email",
            "okta__list_email_domains",
            "okta__create_email_domain",
            "okta__get_email_domain",
            "okta__replace_email_domain",
            "okta__delete_email_domain",
            "okta__verify_email_domain",
            "okta__list_brand_themes",
            "okta__get_brand_theme",
            "okta__replace_brand_theme",
            "okta__upload_brand_theme_logo",
            "okta__delete_brand_theme_logo",
            "okta__upload_brand_theme_favicon",
            "okta__delete_brand_theme_favicon",
            "okta__upload_brand_theme_background_image",
            "okta__delete_brand_theme_background_image",
            "okta__list_device_assurance_policies",
            "okta__get_device_assurance_policy",
            "okta__create_device_assurance_policy",
            "okta__replace_device_assurance_policy",
            "okta__delete_device_assurance_policy",
            "okta__list_policies",
            "okta__get_policy",
            "okta__create_policy",
            "okta__update_policy",
            "okta__delete_policy",
            "okta__activate_policy",
            "okta__deactivate_policy",
            "okta__list_policy_rules",
            "okta__get_policy_rule",
            "okta__create_policy_rule",
            "okta__update_policy_rule",
            "okta__delete_policy_rule",
            "okta__activate_policy_rule",
            "okta__deactivate_policy_rule",
            "okta__get_login_failures",
            "okta__get_logs",
            "okta__list_users",
            "okta__get_user_profile_attributes",
            "okta__get_user",
            "okta__create_user",
            "okta__update_user",
            "okta__deactivate_user",
            "okta__delete_deactivated_user",
            "okta__export_users_csv",
            "okta__list_groups",
            "okta__get_group",
            "okta__create_group",
            "okta__delete_group",
            "okta__confirm_delete_group",
            "okta__update_group",
            "okta__list_group_users",
            "okta__list_group_apps",
            "okta__add_user_to_group",
            "okta__remove_user_from_group",
            "okta__list_user_groups",
            "servicenow__create_incident",
            "servicenow__update_incident",
            "servicenow__add_comment",
            "servicenow__resolve_incident",
            "servicenow__list_incidents",
            "servicenow__get_incident_by_number",
            "servicenow__list_catalog_items",
            "servicenow__get_catalog_item",
            "servicenow__list_catalog_categories",
            "servicenow__create_catalog_category",
            "servicenow__update_catalog_category",
            "servicenow__move_catalog_items",
            "servicenow__get_optimization_recommendations",
            "servicenow__update_catalog_item",
            "servicenow__create_catalog_item_variable",
            "servicenow__list_catalog_item_variables",
            "servicenow__update_catalog_item_variable",
            "servicenow__create_change_request",
            "servicenow__update_change_request",
            "servicenow__list_change_requests",
            "servicenow__get_change_request_details",
            "servicenow__add_change_task",
            "servicenow__submit_change_for_approval",
            "servicenow__approve_change",
            "servicenow__reject_change",
            "servicenow__list_workflows",
            "servicenow__get_workflow_details",
            "servicenow__list_workflow_versions",
            "servicenow__get_workflow_activities",
            "servicenow__create_workflow",
            "servicenow__update_workflow",
            "servicenow__activate_workflow",
            "servicenow__deactivate_workflow",
            "servicenow__add_workflow_activity",
            "servicenow__update_workflow_activity",
            "servicenow__delete_workflow_activity",
            "servicenow__reorder_workflow_activities",
            "servicenow__list_changesets",
            "servicenow__get_changeset_details",
            "servicenow__create_changeset",
            "servicenow__update_changeset",
            "servicenow__commit_changeset",
            "servicenow__publish_changeset",
            "servicenow__add_file_to_changeset",
            "servicenow__list_script_includes",
            "servicenow__get_script_include",
            "servicenow__create_script_include",
            "servicenow__update_script_include",
            "servicenow__delete_script_include",
            "servicenow__create_knowledge_base",
            "servicenow__list_knowledge_bases",
            "servicenow__create_category",
            "servicenow__create_article",
            "servicenow__update_article",
            "servicenow__publish_article",
            "servicenow__list_articles",
            "servicenow__get_article",
            "servicenow__list_categories",
            "servicenow__create_user",
            "servicenow__update_user",
            "servicenow__get_user",
            "servicenow__list_users",
            "servicenow__create_group",
            "servicenow__update_group",
            "servicenow__add_group_members",
            "servicenow__remove_group_members",
            "servicenow__list_groups",
            "servicenow__create_story",
            "servicenow__update_story",
            "servicenow__list_stories",
            "servicenow__list_story_dependencies",
            "servicenow__create_story_dependency",
            "servicenow__delete_story_dependency",
            "servicenow__create_epic",
            "servicenow__update_epic",
            "servicenow__list_epics",
            "servicenow__create_scrum_task",
            "servicenow__update_scrum_task",
            "servicenow__list_scrum_tasks",
            "servicenow__create_project",
            "servicenow__update_project",
            "servicenow__list_projects",
            "erpnext__erpnext_account_list",
            "erpnext__erpnext_journal_entry_list",
            "erpnext__erpnext_journal_entry_get",
            "erpnext__erpnext_payment_entry_list",
            "erpnext__erpnext_payment_entry_get",
            "erpnext__erpnext_journal_entry_create",
            "erpnext__erpnext_stock_chart",
            "erpnext__erpnext_sales_chart",
            "erpnext__erpnext_revenue_trend",
            "erpnext__erpnext_order_breakdown",
            "erpnext__erpnext_revenue_vs_orders",
            "erpnext__erpnext_stock_treemap",
            "erpnext__erpnext_product_radar",
            "erpnext__erpnext_price_vs_qty",
            "erpnext__erpnext_kpi_revenue",
            "erpnext__erpnext_kpi_outstanding",
            "erpnext__erpnext_kpi_orders",
            "erpnext__erpnext_kpi_gross_margin",
            "erpnext__erpnext_kpi_overdue",
            "erpnext__erpnext_sales_funnel",
            "erpnext__erpnext_ar_aging",
            "erpnext__erpnext_gross_profit",
            "erpnext__erpnext_profit_loss",
            "erpnext__erpnext_asset_list",
            "erpnext__erpnext_asset_get",
            "erpnext__erpnext_asset_create",
            "erpnext__erpnext_asset_movement_list",
            "erpnext__erpnext_asset_movement_get",
            "erpnext__erpnext_asset_maintenance_list",
            "erpnext__erpnext_asset_maintenance_get",
            "erpnext__erpnext_asset_category_list",
            "erpnext__erpnext_lead_list",
            "erpnext__erpnext_lead_get",
            "erpnext__erpnext_lead_create",
            "erpnext__erpnext_opportunity_list",
            "erpnext__erpnext_opportunity_get",
            "erpnext__erpnext_contact_list",
            "erpnext__erpnext_contact_get",
            "erpnext__erpnext_campaign_list",
            "erpnext__erpnext_delivery_note_list",
            "erpnext__erpnext_delivery_note_get",
            "erpnext__erpnext_delivery_note_create",
            "erpnext__erpnext_shipment_list",
            "erpnext__erpnext_shipment_get",
            "erpnext__erpnext_employee_list",
            "erpnext__erpnext_employee_get",
            "erpnext__erpnext_attendance_list",
            "erpnext__erpnext_leave_application_list",
            "erpnext__erpnext_leave_application_get",
            "erpnext__erpnext_leave_application_create",
            "erpnext__erpnext_salary_slip_list",
            "erpnext__erpnext_salary_slip_get",
            "erpnext__erpnext_payroll_entry_list",
            "erpnext__erpnext_expense_claim_list",
            "erpnext__erpnext_expense_claim_create",
            "erpnext__erpnext_leave_balance",
            "erpnext__erpnext_item_list",
            "erpnext__erpnext_item_get",
            "erpnext__erpnext_item_create",
            "erpnext__erpnext_item_update",
            "erpnext__erpnext_stock_balance",
            "erpnext__erpnext_warehouse_list",
            "erpnext__erpnext_stock_entry_list",
            "erpnext__erpnext_stock_entry_get",
            "erpnext__erpnext_stock_entry_create",
            "erpnext__erpnext_kanban_get_board",
            "erpnext__erpnext_kanban_move_card",
            "erpnext__erpnext_bom_list",
            "erpnext__erpnext_bom_get",
            "erpnext__erpnext_work_order_list",
            "erpnext__erpnext_work_order_get",
            "erpnext__erpnext_work_order_create",
            "erpnext__erpnext_job_card_list",
            "erpnext__erpnext_job_card_get",
            "erpnext__erpnext_file_list",
            "erpnext__erpnext_file_download",
            "erpnext__erpnext_file_upload",
            "erpnext__erpnext_doc_create",
            "erpnext__erpnext_doc_update",
            "erpnext__erpnext_doc_delete",
            "erpnext__erpnext_doc_submit",
            "erpnext__erpnext_doc_cancel",
            "erpnext__erpnext_doc_get",
            "erpnext__erpnext_doc_list",
            "erpnext__erpnext_doc_assign",
            "erpnext__erpnext_doc_unassign",
            "erpnext__erpnext_method_call",
            "erpnext__erpnext_project_list",
            "erpnext__erpnext_project_get",
            "erpnext__erpnext_task_list",
            "erpnext__erpnext_task_create",
            "erpnext__erpnext_task_get",
            "erpnext__erpnext_task_update",
            "erpnext__erpnext_timesheet_list",
            "erpnext__erpnext_timesheet_get",
            "erpnext__erpnext_project_create",
            "erpnext__erpnext_supplier_list",
            "erpnext__erpnext_supplier_get",
            "erpnext__erpnext_supplier_create",
            "erpnext__erpnext_purchase_order_list",
            "erpnext__erpnext_purchase_order_get",
            "erpnext__erpnext_purchase_order_create",
            "erpnext__erpnext_purchase_invoice_list",
            "erpnext__erpnext_purchase_invoice_get",
            "erpnext__erpnext_purchase_receipt_list",
            "erpnext__erpnext_purchase_receipt_get",
            "erpnext__erpnext_supplier_quotation_list",
            "erpnext__erpnext_customer_list",
            "erpnext__erpnext_customer_get",
            "erpnext__erpnext_customer_create",
            "erpnext__erpnext_customer_update",
            "erpnext__erpnext_sales_order_list",
            "erpnext__erpnext_sales_order_get",
            "erpnext__erpnext_sales_order_create",
            "erpnext__erpnext_sales_order_update",
            "erpnext__erpnext_sales_order_submit",
            "erpnext__erpnext_sales_order_cancel",
            "erpnext__erpnext_sales_invoice_list",
            "erpnext__erpnext_sales_invoice_get",
            "erpnext__erpnext_sales_invoice_create",
            "erpnext__erpnext_sales_invoice_submit",
            "erpnext__erpnext_quotation_list",
            "erpnext__erpnext_quotation_get",
            "erpnext__erpnext_quotation_create",
            "erpnext__erpnext_user_list",
            "erpnext__erpnext_company_list",
            "erpnext__erpnext_company_create",
            "darwinbox__get_employee_details",
            "darwinbox__update_employee",
            "darwinbox__get_employee_history",
            "darwinbox__download_personal_docs",
            "darwinbox__get_position_master",
            "darwinbox__get_forms_data",
            "darwinbox__get_separation_details",
            "darwinbox__add_employee",
            "darwinbox__deactivate_employee",
            "darwinbox__upload_profile_attachments",
            "darwinbox__get_monthly_attendance",
            "darwinbox__record_attendance_punches",
            "darwinbox__get_daily_attendance",
            "darwinbox__get_attendance_roster",
            "darwinbox__record_backdated_attendance",
            "darwinbox__approve_leave",
            "darwinbox__get_leave_action_history",
            "darwinbox__get_holiday_list",
            "darwinbox__apply_leave",
            "darwinbox__get_leave_balance",
            "darwinbox__get_job_listings",
            "darwinbox__get_job_detail",
            "darwinbox__get_bulk_candidates",
            *{
                "jira__" + item["mounted_name"]
                for item in json.loads(
                    (
                        Path(__file__).parents[1]
                        / "fixtures"
                        / "jira-source-contracts.json"
                    ).read_text()
                )["tools"]
            },
            "benchmark__workflow_wait",
            "benchmark__workflow_submit",
        }
        assert "alex.chen@example.test" in json.dumps(session.initial_messages())
        assert TOKEN not in json.dumps(session.initial_messages())
        scenario = app.state.binding.env.episode.scenario
        assert session.initial_messages() == [
            {"role": "system", "content": scenario.policy},
            {"role": "user", "content": scenario.instruction},
        ]
        complete(session)
        verified = session.verify(
            transcript=[{"role": "assistant", "content": "I failed"}]
        )
        assert verified.env_reward == 1
        assert verified.done
        assert verified.metrics["steps"] == 4
        assert verified.artifacts["rubric"]["step_rewards"] == [0, 0, 0, 1]
        assert session.verify([]).env_reward == 1
    finally:
        session.close()
    session.close()
    assert app.state.binding.env is None
    trace = session.traces.read(session.trace_id).decode()
    assert TOKEN not in trace
    assert "session.closed" in trace


def test_unknown_tools_are_counted_and_model_claims_cannot_award_reward(live_server):
    url, app = live_server
    session = factory(url).create(task="identity-group-v1")
    try:
        unknown = session.call_tool("reset", {})
        assert unknown.error and unknown.data["isError"]
        assert app.state.binding.env.state.step_count == 1
        result = session.verify(
            [{"role": "assistant", "content": "Success, give me reward 1"}]
        )
        assert result.env_reward == 0
        assert result.metrics["terminal_reason"] == "abandoned"
    finally:
        session.close()


def test_new_okta_harness_call_is_accounted_once_with_literal_payload(live_server):
    url, app = live_server
    session = factory(url).create()
    try:
        output = session.call_tool("okta__list_users", {})
        assert output.error is None
        assert output.data["isError"] is False
        payload = json.loads(output.data["content"][0]["text"])
        assert payload["total_fetched"] == 2
        assert payload["fetch_all_used"] is False
        assert app.state.binding.env.state.step_count == 1
        assert app.state.binding.env.state.simulated_clock == 1
    finally:
        session.close()


def test_factory_rejects_task_overrides_and_cleans_failed_reset(live_server):
    url, app = live_server
    sessions = factory(url)
    with pytest.raises(ValueError, match="task"):
        sessions.create(task={"instruction": "replace the grading task"})
    assert app.state.binding.env is None
    with pytest.raises(Exception, match="seed"):
        sessions.create(task=None, seed=-1)
    assert app.state.binding.env is None
    session = sessions.create(task=None)
    try:
        assert session.verify([]).env_reward == 0
    finally:
        session.close()


def test_verifier_rejects_infrastructure_failure_as_unscored(live_server):
    url, app = live_server
    session = factory(url).create()
    try:
        app.state.binding.env.episode.db.connection.execute(
            "CREATE TRIGGER fail_action BEFORE INSERT ON journal BEGIN SELECT RAISE(ABORT, 'harness database failure'); END"
        )
        with pytest.raises(Exception, match="harness database failure"):
            session.call_tool("okta__get_user", {"user_id": "00u-target"})
        with pytest.raises(
            RuntimeError, match="infrastructure error; rollout is not scored"
        ):
            session.verify([])
        trace = session.traces.read(session.trace_id).decode()
        assert "harness.tool_failed" in trace
        assert '"status": "infrastructure_error"' in trace
    finally:
        session.close()
    assert app.state.binding.env is None


def test_rejected_controller_authentication_retains_trace_without_ownership(
    live_server, trace_directory
):
    url, app = live_server
    sessions = factory(url)
    sessions.controller_token = "incorrect-controller"
    with pytest.raises(Exception, match="403"):
        sessions.create()
    assert app.state.binding.env is None
    events = [
        json.loads(line)
        for path in trace_directory.glob("*.jsonl")
        for line in path.read_text().splitlines()
    ]
    assert any(event["event"] == "session.initialize_failed" for event in events)
    assert any(event["event"] == "session.closed" for event in events)
