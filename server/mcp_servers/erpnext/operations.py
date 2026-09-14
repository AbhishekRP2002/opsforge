"""Erpnext operations tool declarations."""

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import ConfigDict, Field, with_config
from pydantic.experimental.missing_sentinel import MISSING
from typing_extensions import TypedDict


@with_config(ConfigDict(extra="allow"))
class ErpnextMethodCallInvalidate(TypedDict):
    doctype: Annotated[str, Field(min_length=1)]
    name: Annotated[str, Field(min_length=1)]


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def erpnext_file_list(
        *,
        attached_to_doctype: Annotated[
            str,
            Field(
                min_length=1,
                description="DocType of the document whose attachments to list.",
            ),
        ],
        attached_to_name: Annotated[
            str,
            Field(
                min_length=1,
                description="Name/ID of the document whose attachments to list.",
            ),
        ],
        limit: Annotated[
            float,
            Field(
                ge=1,
                le=500,
                description="Maximum number of files to return. Defaults to 50.",
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List the files attached to an ERPNext document. Returns name, size, privacy and URL for each attachment. Pairs with erpnext_file_upload: that one attaches, this one reads back."
        return await dispatch(
            "erpnext_file_list",
            {
                key: value
                for key, value in {
                    "attached_to_doctype": attached_to_doctype,
                    "attached_to_name": attached_to_name,
                    "limit": limit,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_file_download(
        *,
        file_id: Annotated[
            str,
            Field(
                min_length=1,
                description="Native ERPNext File.name identifier, never a URL.",
            ),
        ],
        attached_to_doctype: Annotated[
            str, Field(min_length=1, description="Expected parent document DocType.")
        ],
        attached_to_name: Annotated[
            str, Field(min_length=1, description="Expected parent document name/ID.")
        ],
    ) -> ToolResult:
        "Download one ERPNext attachment for the document viewer. The tool accepts a File ID, verifies its document attachment, and returns one embedded binary resource."
        return await dispatch(
            "erpnext_file_download",
            {
                "file_id": file_id,
                "attached_to_doctype": attached_to_doctype,
                "attached_to_name": attached_to_name,
            },
        )

    @mcp.tool
    async def erpnext_file_upload(
        *,
        file_name: Annotated[
            str, Field(min_length=1, description="Filename only, without a path.")
        ],
        content_base64: Annotated[
            str,
            Field(
                min_length=1,
                description="File content as standard base64 (not a data URL).",
            ),
        ],
        attached_to_doctype: Annotated[
            str,
            Field(
                min_length=1,
                description="DocType of the document to attach the file to.",
            ),
        ],
        attached_to_name: Annotated[
            str,
            Field(
                min_length=1,
                description="Name/ID of the document to attach the file to.",
            ),
        ],
        attached_to_field: Annotated[
            str,
            Field(
                description="Optional Attach or Attach Image field to populate with the uploaded file."
            ),
        ]
        | MISSING = MISSING,
        is_private: Annotated[
            bool,
            Field(description="Whether the attachment is private. Defaults to true."),
        ] = True,
    ) -> ToolResult:
        "Upload base64-encoded file content and attach it to any ERPNext document. Files are private by default."
        return await dispatch(
            "erpnext_file_upload",
            {
                key: value
                for key, value in {
                    "file_name": file_name,
                    "content_base64": content_base64,
                    "attached_to_doctype": attached_to_doctype,
                    "attached_to_name": attached_to_name,
                    "attached_to_field": attached_to_field,
                    "is_private": is_private,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_doc_create(
        *,
        doctype: Annotated[
            str,
            Field(
                description="ERPNext DocType name (e.g. 'Company', 'Item Group', 'Warehouse Type')"
            ),
        ],
        data: Annotated[
            dict[str, Any],
            Field(
                description="Document fields as key-value pairs. Include 'name' for DocTypes with Prompt naming."
            ),
        ],
    ) -> ToolResult:
        "Create any ERPNext document. Works on any DocType including master data (Company, Item Group, UOM, Territory, Customer Group, Supplier Group, Warehouse Type, etc.). For DocTypes with 'Prompt' naming, include a 'name' field in data. Returns the created document."
        return await dispatch("erpnext_doc_create", {"doctype": doctype, "data": data})

    @mcp.tool
    async def erpnext_doc_update(
        *,
        doctype: Annotated[
            str,
            Field(
                description="ERPNext DocType name (e.g. 'Customer', 'Sales Order', 'Item')"
            ),
        ],
        name: Annotated[
            str, Field(description="Document name/ID (e.g. 'CUST-00001', 'SO-00001')")
        ],
        data: Annotated[
            dict[str, Any],
            Field(
                description="Fields to update as key-value pairs. Only provided fields will be changed."
            ),
        ],
    ) -> ToolResult:
        "Update any ERPNext document (partial update). Works on any DocType. Pass doctype (e.g. 'Customer', 'Sales Order'), the document name, and the fields to change. Returns the updated document."
        return await dispatch(
            "erpnext_doc_update", {"doctype": doctype, "name": name, "data": data}
        )

    @mcp.tool
    async def erpnext_doc_delete(
        *,
        doctype: Annotated[
            str,
            Field(description="ERPNext DocType name (e.g. 'Customer', 'Sales Order')"),
        ],
        name: Annotated[str, Field(description="Document name/ID to delete")],
    ) -> ToolResult:
        "Delete any ERPNext document. Only Draft documents can usually be deleted. For submitted documents, use cancel first. Works on any DocType."
        return await dispatch("erpnext_doc_delete", {"doctype": doctype, "name": name})

    @mcp.tool
    async def erpnext_doc_get(
        *,
        doctype: Annotated[
            str, Field(description="ERPNext DocType name (e.g. 'Lead', 'Asset', 'BOM')")
        ],
        name: Annotated[str, Field(description="Document name/ID")],
    ) -> ToolResult:
        "Get any ERPNext document by DocType and name. Useful for DocTypes not covered by dedicated tools. Returns the full document with all fields."
        return await dispatch("erpnext_doc_get", {"doctype": doctype, "name": name})

    @mcp.tool
    async def erpnext_doc_list(
        *,
        doctype: Annotated[
            str,
            Field(
                description="ERPNext DocType name (e.g. 'Lead', 'Asset', 'BOM', 'Cost Center')"
            ),
        ],
        fields: Annotated[
            list[str],
            Field(
                description="Fields to fetch (default: ['name', 'modified']). Use ['*'] for all fields."
            ),
        ]
        | MISSING = MISSING,
        filters: Annotated[
            list[
                Annotated[
                    tuple[
                        Annotated[str, Field(min_length=1)],
                        Annotated[str, Field(min_length=1)],
                        str | float | bool | None | list[str | float],
                    ],
                    Field(min_length=3, max_length=3),
                ]
                | Annotated[
                    tuple[
                        Annotated[str, Field(min_length=1)],
                        Annotated[str, Field(min_length=1)],
                        Annotated[str, Field(min_length=1)],
                        str | float | bool | None | list[str | float],
                    ],
                    Field(min_length=4, max_length=4),
                ]
                | list[str]
            ],
            Field(
                description='Frappe filters as array of [fieldname, operator, value] tuples, or [child doctype, fieldname, operator, value] to filter on a child table. Values may be strings, numbers, booleans, null, or string/number arrays for in/not in. Example: [["status","=","Open"],["company","=","Acme"]]'
            ),
        ]
        | MISSING = MISSING,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        order_by: Annotated[
            str, Field(description="Order by clause (e.g. 'modified desc', 'name asc')")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List any ERPNext documents by DocType. Useful for DocTypes not covered by dedicated tools. Supports field selection, filters (as JSON array), and limit."
        return await dispatch(
            "erpnext_doc_list",
            {
                key: value
                for key, value in {
                    "doctype": doctype,
                    "fields": fields,
                    "filters": filters,
                    "limit": limit,
                    "order_by": order_by,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_method_call(
        *,
        method: Annotated[
            str,
            Field(
                min_length=1,
                description="Dotted path to the whitelisted method, e.g. 'frappe.client.get_count' or 'my_app.api.reconcile'.",
            ),
        ],
        args: Annotated[
            dict[str, Any], Field(description="Keyword arguments passed to the method.")
        ]
        | MISSING = MISSING,
        http_method: Annotated[
            Literal["GET", "POST"],
            Field(
                description='HTTP verb to use. Defaults to POST. Use GET for methods declared @frappe.whitelist(methods=["GET"]), which reject POST.'
            ),
        ]
        | MISSING = MISSING,
        invalidate: Annotated[
            ErpnextMethodCallInvalidate,
            Field(
                description="Optional { doctype, name } to drop from the read cache after a mutating call, so the next read reflects the method's side effects."
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Call a whitelisted Frappe method directly (POST or GET /api/method/{method}). Escape hatch for behaviour that is not a plain document write: custom-app @frappe.whitelist methods, validate hooks that reject direct field updates, and GET-only endpoints. Deny-by-default: the method must match an entry in ERPNEXT_METHOD_ALLOWLIST (exact dotted path or 'prefix.*' wildcard), or the call is rejected before it reaches ERPNext. Set ERPNEXT_METHOD_ALLOWLIST=* to allow any method for a fully open session."
        return await dispatch(
            "erpnext_method_call",
            {
                key: value
                for key, value in {
                    "method": method,
                    "args": args,
                    "http_method": http_method,
                    "invalidate": invalidate,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_user_list(
        *,
        search: Annotated[str, Field(description="Substring match on full name")]
        | MISSING = MISSING,
        include_disabled: Annotated[
            bool, Field(description="Include disabled users (default false)")
        ]
        | MISSING = MISSING,
        limit: Annotated[float, Field(description="Max results (default 50)")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List assignable ERPNext users. Defaults to enabled System Users, excluding Administrator and Guest — the population valid for document assignment (erpnext_doc_assign, task assign_to). Fields: name (email), full_name, enabled."
        return await dispatch(
            "erpnext_user_list",
            {
                key: value
                for key, value in {
                    "search": search,
                    "include_disabled": include_disabled,
                    "limit": limit,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_company_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List ERPNext companies. Fields: name, abbr, default_currency, country, domain."
        return await dispatch(
            "erpnext_company_list",
            {
                key: value
                for key, value in {"limit": limit}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_company_create(
        *,
        company_name: Annotated[str, Field(description="Company name")],
        abbr: Annotated[
            str, Field(description="Abbreviation (e.g. CI for Casys Industries)")
        ],
        default_currency: Annotated[
            str, Field(description="Currency code (e.g. EUR, USD)")
        ],
        country: Annotated[
            str, Field(description="Country name (e.g. France, United States)")
        ],
        domain: Annotated[
            str,
            Field(
                description="Business domain (Manufacturing, Services, Retail, Distribution, Education, etc.)"
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create an ERPNext Company. Requires company_name, abbr, default_currency, country. Prerequisites: Warehouse Type 'Transit' and 'Default' must exist. Use erpnext_doc_create to create them first if needed."
        return await dispatch(
            "erpnext_company_create",
            {
                key: value
                for key, value in {
                    "company_name": company_name,
                    "abbr": abbr,
                    "default_currency": default_currency,
                    "country": country,
                    "domain": domain,
                }.items()
                if value is not MISSING
            },
        )

    return (
        erpnext_file_list,
        erpnext_file_download,
        erpnext_file_upload,
        erpnext_doc_create,
        erpnext_doc_update,
        erpnext_doc_delete,
        erpnext_doc_get,
        erpnext_doc_list,
        erpnext_method_call,
        erpnext_user_list,
        erpnext_company_list,
        erpnext_company_create,
    )
