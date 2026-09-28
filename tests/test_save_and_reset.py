"""POST /config and POST /config/reset.

The save route has one rule that is easy to break and invisible from the page:
it writes a key to the user configuration only when the value differs from the
default, and it removes the key when the value returns to the default. That rule
is what keeps the user configuration an overlay rather than a full copy of the
defaults, and most of the tests here are about it.
"""
import json

import pytest
import yaml
from ovos_config.config import DefaultConfig

import ovos_yaml_editor

from conftest import GOOD_AUTH


def read_user_config(path):
    with open(path) as f:
        return json.load(f)


def save(client, data, fmt="yaml"):
    return client.post("/config", json={"data": data, "format": fmt},
                       auth=GOOD_AUTH).json()


def test_save_yaml_writes_a_non_default_value(client, user_config_path):
    assert save(client, "lang: pt-pt\n") == {"success": True}
    assert read_user_config(user_config_path)["lang"] == "pt-pt"


def test_save_json_writes_a_non_default_value(client, user_config_path):
    assert save(client, '{"lang": "es-es"}', "json") == {"success": True}
    assert read_user_config(user_config_path)["lang"] == "es-es"


def test_yaml_and_json_save_the_same_way(client, user_config_path):
    save(client, "lang: fr-fr\n")
    from_yaml = read_user_config(user_config_path)
    save(client, '{"lang": "fr-fr"}', "json")
    assert read_user_config(user_config_path) == from_yaml


def test_format_defaults_to_yaml_when_absent(client, user_config_path):
    """The body key is optional and the route falls back to yaml."""
    r = client.post("/config", json={"data": "lang: da-dk\n"}, auth=GOOD_AUTH)
    assert r.json() == {"success": True}
    assert read_user_config(user_config_path)["lang"] == "da-dk"


def test_a_value_equal_to_the_default_is_not_written(client, user_config_path):
    """The user configuration stays an overlay, not a copy of the defaults."""
    default_lang = DefaultConfig().get("lang")
    assert save(client, f"lang: {default_lang}\n") == {"success": True}
    assert "lang" not in read_user_config(user_config_path)


def test_a_value_returned_to_the_default_is_removed(client, user_config_path):
    """The branch that pops the key again. This is the one worth guarding."""
    default_lang = DefaultConfig().get("lang")
    assert save(client, "lang: pt-pt\n") == {"success": True}
    assert read_user_config(user_config_path)["lang"] == "pt-pt"
    assert save(client, f"lang: {default_lang}\n") == {"success": True}
    assert "lang" not in read_user_config(user_config_path)


def test_a_key_absent_from_the_defaults_is_written(client, user_config_path):
    """The `v2 is None` branch: an unknown key has no default to compare to."""
    assert save(client, "zzz_not_a_default_key: 42\n") == {"success": True}
    assert read_user_config(user_config_path)["zzz_not_a_default_key"] == 42


def test_save_updates_the_in_memory_config(client):
    """The read routes serve memory_config, so a save must update it too."""
    assert save(client, "lang: eu-es\n") == {"success": True}
    assert ovos_yaml_editor.memory_config["lang"] == "eu-es"


def test_save_leaves_other_keys_alone(client, user_config_path):
    """A partial save must not drop a key the payload does not mention."""
    save(client, "lang: gl-es\n")
    save(client, "zzz_other: 1\n")
    stored = read_user_config(user_config_path)
    assert stored["lang"] == "gl-es"
    assert stored["zzz_other"] == 1


def test_nested_value_round_trips(client, user_config_path):
    assert save(client, "tts:\n  module: ovos-tts-plugin-test\n") == {"success": True}
    assert read_user_config(user_config_path)["tts"]["module"] == \
        "ovos-tts-plugin-test"


def test_saved_yaml_can_be_read_back_as_yaml(client):
    """The full round trip the editor performs: save, then reload the tab."""
    assert save(client, "lang: nl-nl\n") == {"success": True}
    reloaded = yaml.safe_load(client.get("/config/yaml", auth=GOOD_AUTH).text)
    assert reloaded["lang"] == "nl-nl"


@pytest.mark.parametrize("bad,fmt", [
    ("a: [unclosed", "yaml"),
    ("\tliteral tab: 1", "yaml"),
    ("{nope", "json"),
    ("", "json"),
])
def test_unparseable_payload_is_reported_not_raised(client, bad, fmt):
    """A syntax error must come back as a message, and must not write."""
    result = save(client, bad, fmt)
    assert result["success"] is False
    assert result["error"]


def test_unparseable_payload_does_not_write(client, user_config_path):
    save(client, "lang: ca-es\n")
    before = read_user_config(user_config_path)
    assert save(client, "a: [unclosed")["success"] is False
    assert read_user_config(user_config_path) == before


@pytest.mark.parametrize("payload", ["just a string", "- a\n- b\n", "42", ""])
def test_a_payload_that_is_not_a_mapping_is_reported(client, payload):
    """Valid YAML that is not a mapping. The route has no .items() to call.

    Recorded as it behaves: the outer try turns it into success:false. The error
    text is a raw Python AttributeError, which is not a message for a user, but
    the request is refused and nothing is written, which is what matters most.
    """
    result = save(client, payload)
    assert result["success"] is False
    assert "has no attribute 'items'" in result["error"]


def test_a_payload_that_is_not_a_mapping_does_not_write(client, user_config_path):
    save(client, "lang: de-de\n")
    before = read_user_config(user_config_path)
    assert save(client, "just a string")["success"] is False
    assert read_user_config(user_config_path) == before


def test_missing_data_key_is_reported(client):
    """An empty body. data defaults to "" and parses to None."""
    r = client.post("/config", json={}, auth=GOOD_AUTH)
    assert r.json()["success"] is False


def test_non_json_request_body_raises(client):
    """DEFECT, recorded not endorsed: this is an unhandled 500.

    ``body = await request.json()`` is outside the try block, so a body that is
    not JSON raises JSONDecodeError out of the route instead of being reported
    as success:false like every other bad input. When that is fixed this test
    must change to expect a 400 or a success:false body.
    """
    with pytest.raises(json.JSONDecodeError):
        client.post("/config", content=b"not json at all", auth=GOOD_AUTH)


def test_reset_empties_the_user_config(client, user_config_path):
    assert save(client, "lang: sv-se\n") == {"success": True}
    assert read_user_config(user_config_path)["lang"] == "sv-se"
    assert client.post("/config/reset", auth=GOOD_AUTH).json() == {"success": True}
    assert read_user_config(user_config_path) == {}


def test_reset_restores_the_default_in_memory(client):
    assert save(client, "lang: sv-se\n") == {"success": True}
    assert ovos_yaml_editor.memory_config["lang"] == "sv-se"
    client.post("/config/reset", auth=GOOD_AUTH)
    assert ovos_yaml_editor.memory_config["lang"] == DefaultConfig().get("lang")


def test_reset_is_idempotent(client, user_config_path):
    """Run a destructive operation twice. The second must not fail."""
    save(client, "lang: sv-se\n")
    assert client.post("/config/reset", auth=GOOD_AUTH).json() == {"success": True}
    assert client.post("/config/reset", auth=GOOD_AUTH).json() == {"success": True}
    assert read_user_config(user_config_path) == {}


def test_save_after_reset_works(client, user_config_path):
    """Reset must not leave the configuration in a state that cannot be written."""
    save(client, "lang: sv-se\n")
    client.post("/config/reset", auth=GOOD_AUTH)
    assert save(client, "lang: fi-fi\n") == {"success": True}
    assert read_user_config(user_config_path)["lang"] == "fi-fi"
