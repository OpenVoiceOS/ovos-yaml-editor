"""The HTTP basic credential check, and what each route does without it."""
import pytest

import ovos_yaml_editor
from ovos_yaml_editor import authenticate
from fastapi.security import HTTPBasicCredentials

from conftest import GOOD_AUTH, BAD_AUTH

# Every route that authenticate() guards.
GUARDED_GET = ["/", "/config/yaml", "/config/json"]


def test_default_credentials_are_admin_password():
    """The fallback when EDITOR_USERNAME and EDITOR_PASSWORD are unset.

    These defaults are public, and the editor they protect can rewrite the whole
    configuration. The test records them so a change to the fallback is a
    deliberate, visible change.
    """
    assert ovos_yaml_editor.USER == "admin"
    assert ovos_yaml_editor.PASSWORD == "password"


def test_authenticate_accepts_the_configured_pair():
    creds = HTTPBasicCredentials(username=ovos_yaml_editor.USER,
                                 password=ovos_yaml_editor.PASSWORD)
    assert authenticate(creds) is True


@pytest.mark.parametrize("username,password", [
    ("admin", "wrong"),
    ("wrong", "password"),
    ("wrong", "wrong"),
    ("", ""),
    ("ADMIN", "password"),      # the username check is case sensitive
    ("admin", "PASSWORD"),      # so is the password check
    ("admin ", "password"),     # no trimming
    ("admin", "password "),
])
def test_authenticate_rejects_anything_else(username, password):
    creds = HTTPBasicCredentials(username=username, password=password)
    assert authenticate(creds) is False


@pytest.mark.parametrize("path", GUARDED_GET)
def test_no_credentials_is_401(client, path):
    """HTTPBasic itself answers a missing header, before authenticate() runs."""
    r = client.get(path)
    assert r.status_code == 401


@pytest.mark.parametrize("path", GUARDED_GET)
def test_wrong_credentials_redirects_to_login(client, path):
    """Current behaviour: a wrong password is a redirect, not a 401.

    DEFECT, recorded not endorsed: /login does not exist (see
    test_login_route_does_not_exist), so a wrong password ends at a 404 and a
    browser is never challenged again. When that is fixed this test must change
    to expect 401.
    """
    r = client.get(path, auth=BAD_AUTH)
    assert r.status_code == 307
    assert r.headers["location"] == "/login"


def test_wrong_credentials_never_returns_config(client):
    """The redirect must not carry configuration in its body."""
    r = client.get("/config/yaml", auth=BAD_AUTH)
    assert r.status_code == 307
    assert "lang" not in r.text


def test_login_route_does_not_exist(client):
    """The target every guarded route redirects a wrong password to.

    DEFECT, recorded not endorsed. The redirect goes nowhere.
    """
    assert client.get("/login").status_code == 404


def test_post_config_wrong_credentials_does_not_write(client, user_config_path):
    r = client.post("/config", json={"data": "lang: de-de", "format": "yaml"},
                    auth=BAD_AUTH)
    assert r.status_code == 307
    with open(user_config_path) as f:
        assert "de-de" not in f.read()


def test_post_reset_wrong_credentials_does_not_clear(client, user_config_path):
    """A wrong password must not be able to erase the configuration."""
    assert client.post("/config", json={"data": "lang: nl-nl", "format": "yaml"},
                       auth=GOOD_AUTH).json() == {"success": True}
    r = client.post("/config/reset", auth=BAD_AUTH)
    assert r.status_code == 307
    with open(user_config_path) as f:
        assert "nl-nl" in f.read()
