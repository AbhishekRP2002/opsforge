from importlib.util import find_spec
from pathlib import Path

from itops_env.server import mcp_servers

PROVIDER_MODULES = {
    "benchmark": (),
    "okta": (
        "applications",
        "customization",
        "devices",
        "logs",
        "pages",
        "policies",
        "templates",
        "themes",
    ),
    "servicenow": (
        "agile",
        "catalog",
        "changes",
        "changesets",
        "incidents",
        "knowledge",
        "optimization",
        "scripts",
        "users",
        "variables",
        "workflows",
    ),
    "erpnext": (
        "accounting_hr",
        "analytics",
        "business",
        "commerce",
        "kanban",
        "operations",
        "projects",
    ),
    "darwinbox": ("attendance", "core", "masters", "recruitment", "timeoff"),
}


def test_mcp_declarations_are_grouped_by_provider_package():
    root = Path(mcp_servers.__file__).parent
    for provider, families in PROVIDER_MODULES.items():
        package = root / provider
        assert package.is_dir()
        assert (package / "__init__.py").is_file()
        assert not (root / f"{provider}.py").exists()
        provider_spec = find_spec(f"itops_env.server.mcp_servers.{provider}")
        assert provider_spec is not None
        assert provider_spec.submodule_search_locations is not None
        for family in families:
            assert (package / f"{family}.py").is_file()
            assert (
                find_spec(f"itops_env.server.mcp_servers.{provider}.{family}")
                is not None
            )
            assert not (root / f"{provider}_{family}.py").exists()
