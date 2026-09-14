from .test_okta_applications import call
from .test_okta_applications import env as env_fixture

env = env_fixture

import pytest


def test_brands_domains_email_references_and_headless_delete(env):
    brand, error = call(env, "create_brand", name="Acme")
    assert not error and brand["name"] == "Acme"
    bid = brand["id"]
    assert call(env, "create_brand", name="Acme")[1]
    assert not call(env, "create_brand", name="acme")[1]
    assert call(env, "list_brands", q="ACME")[0]["total_fetched"] == 2
    assert not call(env, "replace_brand", brand_id=bid, name="New", locale="fr")[1]
    assert call(env, "get_brand", brand_id=bid)[0]["locale"] == "fr"
    domain, error = call(
        env,
        "create_custom_domain",
        domain="login.example.test",
        certificate_source_type=" manual ",
    )
    assert not error and domain["validationStatus"] == "NOT_STARTED"
    did = domain["id"]
    assert call(env, "replace_custom_domain", domain_id=did, brand_id="missing")[1]
    assert (
        call(env, "replace_custom_domain", domain_id=did, brand_id=bid)[0]["brandId"]
        == bid
    )
    assert call(env, "list_brand_domains", brand_id=bid)[0]["domains"][0]["id"] == did
    assert call(env, "list_custom_domains")[0]["total_fetched"] >= 1
    assert (
        call(env, "verify_custom_domain", domain_id=did)[0]["validationStatus"]
        == "VERIFIED"
    )
    assert (
        call(env, "get_custom_domain", domain_id=did)[0]["validationStatus"]
        == "VERIFIED"
    )
    assert call(env, "delete_custom_domain", domain_id=did)[0]["success"] is False
    assert not call(env, "get_custom_domain", domain_id=did)[1]
    email, error = call(
        env,
        "create_email_domain",
        brand_id=bid,
        domain="mail.example.test",
        display_name="Support",
        user_name="help",
    )
    assert not error and email["brandId"] == bid
    eid = email["id"]
    assert (
        call(
            env,
            "replace_email_domain",
            email_domain_id=eid,
            display_name="Security",
            user_name="security",
        )[0]["displayName"]
        == "Security"
    )
    assert (
        call(env, "verify_email_domain", email_domain_id=eid)[0]["validationStatus"]
        == "VERIFIED"
    )
    assert (
        call(env, "get_email_domain", email_domain_id=eid, expand_brands=True)[0][
            "_embedded"
        ]["brands"][0]["id"]
        == bid
    )
    assert call(env, "list_email_domains")[0]["total_fetched"] == 1
    assert call(env, "delete_email_domain", email_domain_id=eid)[0]["success"] is False
    assert not call(env, "get_email_domain", email_domain_id=eid)[1]
    assert call(env, "delete_brand", brand_id=bid)[0]["confirmation_required"] is True
    assert not call(env, "get_brand", brand_id=bid)[1]


def test_certificate_uses_only_episode_artifact_and_preserves_key_privacy(env):
    domain, error = call(
        env,
        "create_custom_domain",
        domain="cert.example.test",
        certificate_source_type="MANUAL",
    )
    assert not error
    did = domain["id"]
    assert call(
        env,
        "upsert_custom_domain_certificate",
        domain_id=did,
        certificate="inert certificate",
        certificate_chain="inert chain",
        private_key_file_path="/etc/passwd",
    )[1]
    result, error = call(
        env,
        "upsert_custom_domain_certificate",
        domain_id=did,
        certificate="inert certificate",
        certificate_chain="inert chain",
        private_key_file_path="/tmp/okta-fixture.key",
    )
    assert not error and result["success"] is True
    read, error = call(env, "get_custom_domain", domain_id=did)
    assert not error and read["certificateSourceType"] == "MANUAL"
    assert "privateKey" not in read


@pytest.mark.parametrize(
    "upload,delete,field",
    [
        ("upload_brand_theme_logo", "delete_brand_theme_logo", "logo"),
        ("upload_brand_theme_favicon", "delete_brand_theme_favicon", "favicon"),
        (
            "upload_brand_theme_background_image",
            "delete_brand_theme_background_image",
            "backgroundImage",
        ),
    ],
)
def test_theme_asset_upload_is_owned_and_headless_delete_retains_asset(
    env, upload, delete, field
):
    brand, _ = call(env, "create_brand", name="Theme")
    bid = brand["id"]
    themes, error = call(env, "list_brand_themes", brand_id=bid)
    assert not error and themes["total_fetched"] == 1
    tid = themes["themes"][0]["id"]
    assert call(env, upload, brand_id=bid, theme_id=tid, file_path="/etc/passwd")[1]
    uploaded, error = call(
        env, upload, brand_id=bid, theme_id=tid, file_path="/tmp/okta-fixture.svg"
    )
    assert not error and uploaded["url"].startswith("episode-artifact:")
    assert (
        call(env, "get_brand_theme", brand_id=bid, theme_id=tid)[0][field]
        == uploaded["url"]
    )
    assert call(env, delete, brand_id=bid, theme_id=tid)[0]["success"] is False
    assert (
        call(env, "get_brand_theme", brand_id=bid, theme_id=tid)[0][field]
        == uploaded["url"]
    )
    other, _ = call(env, "create_brand", name="Other")
    assert call(env, "get_brand_theme", brand_id=other["id"], theme_id=tid)[1]


def test_theme_replacement_validates_variants(env):
    brand, _ = call(env, "create_brand", name="Colors")
    bid = brand["id"]
    tid = call(env, "list_brand_themes", brand_id=bid)[0]["themes"][0]["id"]
    args = {
        "brand_id": bid,
        "theme_id": tid,
        "primary_color_hex": "#000000",
        "secondary_color_hex": "#ffffff",
        "sign_in_page_touch_point_variant": "OKTA_DEFAULT",
        "end_user_dashboard_touch_point_variant": "FULL_THEME",
        "error_page_touch_point_variant": "OKTA_DEFAULT",
        "email_template_touch_point_variant": "FULL_THEME",
    }
    assert not call(env, "replace_brand_theme", **args)[1]
    assert (
        call(env, "get_brand_theme", brand_id=bid, theme_id=tid)[0]["primaryColorHex"]
        == "#000000"
    )
    assert call(
        env,
        "replace_brand_theme",
        **(args | {"email_template_touch_point_variant": "INVALID"}),
    )[1]
