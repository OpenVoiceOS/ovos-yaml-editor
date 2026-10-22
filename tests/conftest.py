"""Test fixtures for ovos-yaml-editor.

This module redirects the OVOS configuration into a temporary directory BEFORE
anything imports ``ovos_config``, and it refuses to run if that redirection did
not take.

Why that matters more than usual here: the application writes to and clears
``USER_CONFIG``. ``POST /config/reset`` calls ``conf.clear()`` then
``conf.store()``. ``USER_CONFIG`` is resolved once, when
``ovos_config.locations`` is first imported, from ``XDG_CONFIG_HOME``. So a suite
that imports the application before setting the environment would point every
test at the real user configuration and the reset test would erase it. The guard
below is the thing that makes this suite safe to run on a developer machine or
on a device, not a formality.
"""
import os
import shutil
import tempfile

# Set the environment first. Nothing above this line may import ovos_config.
_TMP = tempfile.mkdtemp(prefix="ovos-yaml-editor-tests-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_TMP, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_TMP, "data")
os.environ["XDG_CACHE_HOME"] = os.path.join(_TMP, "cache")
# A stale XDG_CONFIG_DIRS would add a system config to the search path.
os.environ["XDG_CONFIG_DIRS"] = os.path.join(_TMP, "xdg_config_dirs")

from ovos_config.locations import USER_CONFIG  # noqa: E402

if not os.path.abspath(USER_CONFIG).startswith(os.path.abspath(_TMP)):
    # Do not let the suite touch a real configuration file.
    raise RuntimeError(
        f"refusing to run: USER_CONFIG is {USER_CONFIG!r}, which is outside the "
        f"temporary directory {_TMP!r}. These tests clear and rewrite "
        "USER_CONFIG, so running them against a real configuration would "
        "destroy it. Something imported ovos_config before this conftest set "
        "XDG_CONFIG_HOME.")

import pytest  # noqa: E402
import ovos_yaml_editor  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# The credentials the module falls back to when EDITOR_USERNAME and
# EDITOR_PASSWORD are unset. Read from the module rather than repeated, so the
# suite follows the module if the defaults change.
GOOD_AUTH = (ovos_yaml_editor.USER, ovos_yaml_editor.PASSWORD)
BAD_AUTH = (ovos_yaml_editor.USER, ovos_yaml_editor.PASSWORD + "-wrong")


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture
def user_config_path():
    """Where the application writes the user configuration."""
    return USER_CONFIG


@pytest.fixture(autouse=True)
def clean_config():
    """Give every test an empty user configuration and a clean memory config.

    ``memory_config`` is a module global that the save route mutates, so without
    this the tests would leak state into each other and the order they run in
    would change the result.
    """
    os.makedirs(os.path.dirname(USER_CONFIG), exist_ok=True)
    with open(USER_CONFIG, "w") as f:
        f.write("{}")
    ovos_yaml_editor.memory_config.reset()
    yield
    if os.path.exists(USER_CONFIG):
        os.remove(USER_CONFIG)


@pytest.fixture
def client():
    """A client that does not follow redirects.

    The routes answer a wrong password with a redirect. Following it would hide
    the status code the test is about.
    """
    return TestClient(ovos_yaml_editor.app, follow_redirects=False)
