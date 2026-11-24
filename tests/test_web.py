from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from roboreka.config import AppConfig, load_config
from roboreka.web import ArmControlAPI


@pytest.fixture
def dashboard(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[sip]\nport = 5060\n", encoding="utf-8")
    config = AppConfig()
    arm = SimpleNamespace(
        current_angles={joint.name: joint.home_angle for joint in config.arm.joints},
        target_angles={joint.name: joint.home_angle for joint in config.arm.joints},
    )
    app = SimpleNamespace(
        config=config,
        arm=arm,
        sip_server=SimpleNamespace(calls={}),
    )
    server = ArmControlAPI(app, config_path, port=0)
    server.start()
    try:
        yield server
    finally:
        server.stop()


def _request(dashboard, path: str, *, method: str = "GET", data: bytes | None = None, headers=None):
    port = dashboard._httpd.server_port
    request_headers = dict(headers or {})
    if data is not None:
        request_headers["Content-Type"] = "application/json"
        request_headers["Origin"] = f"http://127.0.0.1:{port}"
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers=request_headers,
        method=method,
    )
    with urlopen(request, timeout=3) as response:
        return response.status, response.read()


def test_dashboard_shows_runtime_status_and_recent_logs(dashboard):
    logging.getLogger("test.web").warning("dashboard test log")

    _, status_body = _request(dashboard, "/api/status")
    status = json.loads(status_body)
    assert status["active_calls"] == 0
    assert status["i2c"]["bus"] == 0
    assert status["arm"]["joint_count"] == 4
    assert status["arm"]["call_action_running"] is False

    _, logs_body = _request(dashboard, "/api/logs")
    assert "dashboard test log" in json.loads(logs_body)["logs"][-1]["message"]


def test_dashboard_saves_valid_config_and_rejects_invalid_toml(dashboard):
    original = dashboard.config_path.read_text(encoding="utf-8")
    invalid = json.dumps({"content": "[sip\nport = 5061"}).encode("utf-8")
    with pytest.raises(HTTPError) as error:
        _request(dashboard, "/api/config", method="POST", data=invalid)
    assert error.value.code == 400
    assert dashboard.config_path.read_text(encoding="utf-8") == original

    invalid_shape = json.dumps({"content": 'sip = "not a table"\n'}).encode("utf-8")
    with pytest.raises(HTTPError) as error:
        _request(dashboard, "/api/config", method="POST", data=invalid_shape)
    assert error.value.code == 400
    assert dashboard.config_path.read_text(encoding="utf-8") == original

    valid = json.dumps({"content": "[sip]\nport = 5062\n"}).encode("utf-8")
    _, body = _request(dashboard, "/api/config", method="POST", data=valid)
    assert "restart" in json.loads(body)["message"].lower()
    assert dashboard.config_path.read_text(encoding="utf-8") == "[sip]\nport = 5062\n"


def test_dashboard_rejects_cross_origin_config_edits(dashboard):
    port = dashboard._httpd.server_port
    data = json.dumps({"content": "[sip]\nport = 5099\n"}).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:{port}/api/config",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Origin": "http://attacker.example",
        },
        method="POST",
    )
    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=3)
    assert error.value.code == 403
    assert dashboard.config_path.read_text(encoding="utf-8") == "[sip]\nport = 5060\n"


def test_dashboard_config_is_read_only_without_config_path(tmp_path):
    config = AppConfig()
    arm = SimpleNamespace(
        current_angles={joint.name: joint.home_angle for joint in config.arm.joints},
        target_angles={joint.name: joint.home_angle for joint in config.arm.joints},
    )
    app = SimpleNamespace(config=config, arm=arm, sip_server=SimpleNamespace(calls={}))
    server = ArmControlAPI(app, None, port=0)
    server.start()
    try:
        _, body = _request(server, "/api/config")
        result = json.loads(body)
        assert result["editable"] is False
        assert result["content"] == ""
    finally:
        server.stop()


def test_visual_action_sequence_saves_and_replaces_toml_blocks(dashboard):
    dashboard.config_path.write_text(
        "[arm]\nhome_on_start = true\n\n"
        "[[arm.joints]]\nname = \"base\"\nchannel = 7\n"
        "min_angle = 0.0\nmax_angle = 180.0\nhome_angle = 90.0\n",
        encoding="utf-8",
    )
    poses = [
        {"angles": {"base": 120.0}, "hold_s": 0.5},
        {"angles": {"base": 90.0}, "hold_s": 0.0},
    ]
    data = json.dumps({"poses": poses}).encode("utf-8")
    _, body = _request(dashboard, "/api/action-sequence", method="POST", data=data)
    result = json.loads(body)
    assert "Saved 2 pose block(s)" in result["message"]
    assert result["config"].index("[[arm.call_sequence]]") < result["config"].index("[[arm.joints]]")

    saved = dashboard.config_path.read_text(encoding="utf-8")
    parsed = load_config(dashboard.config_path)
    assert [pose.angles for pose in parsed.arm.call_sequence] == [{"base": 120.0}, {"base": 90.0}]
    assert parsed.arm.joints[0].channel == 7

    replacement = json.dumps(
        {"poses": [{"angles": {"base": 100.0}, "hold_s": 0.0}]}
    ).encode("utf-8")
    _request(dashboard, "/api/action-sequence", method="POST", data=replacement)
    assert dashboard.config_path.read_text(encoding="utf-8").count("[[arm.call_sequence]]") == 1
    assert "[[arm.joints]]" in saved
    assert load_config(dashboard.config_path).arm.call_sequence[0].angles == {"base": 100.0}

    empty = json.dumps({"poses": []}).encode("utf-8")
    _request(dashboard, "/api/action-sequence", method="POST", data=empty)
    final_config = dashboard.config_path.read_text(encoding="utf-8")
    assert "[[arm.call_sequence]]" not in final_config
    assert load_config(dashboard.config_path).arm.call_sequence == []


def test_visual_action_sequence_rejects_out_of_range_angles(dashboard):
    original = dashboard.config_path.read_text(encoding="utf-8")
    data = json.dumps(
        {"poses": [{"angles": {"base": 181.0}, "hold_s": 0.0}]}
    ).encode("utf-8")
    with pytest.raises(HTTPError) as error:
        _request(dashboard, "/api/action-sequence", method="POST", data=data)
    assert error.value.code == 400
    assert dashboard.config_path.read_text(encoding="utf-8") == original


def test_visual_action_sequence_supports_wait_only_poses(dashboard):
    poses = [
        {"angles": {"base": 120.0}, "hold_s": 0.0},
        {"angles": {}, "hold_s": 1.25},
    ]
    data = json.dumps({"poses": poses}).encode("utf-8")
    _, body = _request(dashboard, "/api/action-sequence", method="POST", data=data)
    result = json.loads(body)
    assert "angles = {}" in result["config"]

    parsed = load_config(dashboard.config_path)
    assert [pose.angles for pose in parsed.arm.call_sequence] == [{"base": 120.0}, {}]
    assert [pose.hold_s for pose in parsed.arm.call_sequence] == [0.0, 1.25]

    _, loaded_body = _request(dashboard, "/api/action-sequence")
    loaded = json.loads(loaded_body)
    assert loaded["poses"] == [{"angles": {"base": 120.0}, "hold_s": 0.0}, {"angles": {}, "hold_s": 1.25}]
