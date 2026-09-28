"""GET /status and GET /config/{format}."""
import json

import pytest
import yaml

import ovos_yaml_editor
from ovos_yaml_editor.version import VERSION_STR

from conftest import GOOD_AUTH


def test_status_needs_no_credentials(client):
    """/status is deliberately open; it is the container health check."""
    r = client.get("/status")
    assert r.status_code == 200
    assert r.json() == {"version": VERSION_STR}


def test_editor_page_is_served_to_a_valid_user(client):
    r = client.get("/", auth=GOOD_AUTH)
    assert r.status_code == 200
    assert "OpenVoiceOS Config Editor" in r.text
    assert "text/html" in r.headers["content-type"]


def test_editor_page_offers_both_tabs(client):
    """The page must drive both formats the config route serves."""
    body = client.get("/", auth=GOOD_AUTH).text
    assert "switchTab('yaml')" in body
    assert "switchTab('json')" in body


def test_config_yaml_is_parseable_yaml(client):
    r = client.get("/config/yaml", auth=GOOD_AUTH)
    assert r.status_code == 200
    loaded = yaml.safe_load(r.text)
    assert isinstance(loaded, dict)
    assert "lang" in loaded


def test_config_json_is_parseable_json(client):
    r = client.get("/config/json", auth=GOOD_AUTH)
    assert r.status_code == 200
    loaded = json.loads(r.text)
    assert isinstance(loaded, dict)
    assert "lang" in loaded


def test_yaml_and_json_describe_the_same_config(client):
    """The two tabs must not disagree about the configuration."""
    as_yaml = yaml.safe_load(client.get("/config/yaml", auth=GOOD_AUTH).text)
    as_json = json.loads(client.get("/config/json", auth=GOOD_AUTH).text)
    assert as_yaml == as_json


def test_both_formats_are_served_as_plain_text(client):
    """The editor loads the body with response.text(), so not as a download."""
    for fmt in ("yaml", "json"):
        r = client.get(f"/config/{fmt}", auth=GOOD_AUTH)
        assert r.headers["content-type"].startswith("text/plain")


def test_config_reflects_a_saved_value(client):
    assert client.post("/config", json={"data": "lang: it-it", "format": "yaml"},
                       auth=GOOD_AUTH).json() == {"success": True}
    assert yaml.safe_load(
        client.get("/config/yaml", auth=GOOD_AUTH).text)["lang"] == "it-it"


def test_yaml_is_block_style_not_flow_style(client):
    """default_flow_style=False. Flow style would be valid YAML and unreadable."""
    body = client.get("/config/yaml", auth=GOOD_AUTH).text
    assert "\n" in body.strip()
    assert not body.lstrip().startswith("{")


def test_json_is_indented(client):
    """indent=2, so the editor opens on something a human can read."""
    body = client.get("/config/json", auth=GOOD_AUTH).text
    assert "\n  " in body


def test_json_does_not_escape_non_ascii(client):
    """ensure_ascii=False. A locale name must survive the round trip readable."""
    assert client.post(
        "/config", json={"data": '{"tts": {"module": "caf\\u00e9"}}',
                         "format": "json"}, auth=GOOD_AUTH).json()["success"]
    body = client.get("/config/json", auth=GOOD_AUTH).text
    assert "café" in body
    assert "caf\\u00e9" not in body


@pytest.mark.parametrize("fmt", ["xml", "toml", "YAML", "Json", "yaml2"])
def test_unsupported_format_reports_an_error(client, fmt):
    """Current behaviour: HTTP 200 with a success:false body.

    The format match is case sensitive, so "YAML" and "Json" are unsupported.

    DEFECT, recorded not endorsed: an unsupported format is a bad request and
    should be a 4xx. The editor only ever asks for yaml or json, so this is not
    reachable from the page, only from a hand-made request. When that is fixed
    this test must change to expect 400.
    """
    r = client.get(f"/config/{fmt}", auth=GOOD_AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": False, "error": "Unsupported format"}


def test_an_empty_format_does_not_reach_the_config_route(client):
    """GET /config/ is not the config route with an empty format.

    Starlette's redirect_slashes sends it to /config, which only accepts POST.
    Recorded because "" looks like it should reach the unsupported-format branch
    and does not.
    """
    r = client.get("/config/", auth=GOOD_AUTH)
    assert r.status_code == 307
    assert r.headers["location"].endswith("/config")
    assert client.get("/config", auth=GOOD_AUTH).status_code == 405
