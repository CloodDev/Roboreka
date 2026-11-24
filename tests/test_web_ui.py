from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from roboreka.config import AppConfig, I2CConfig, SIPConfig
from roboreka.i2c.pca9685 import PCA9685
from roboreka.voip.server import RoborekaServer
from roboreka.web import ArmControlAPI
from roboreka.web_ui import WebUIApplication


def _request(port: int, path: str, *, method: str = "GET", data: bytes | None = None):
    headers = {}
    if data is not None:
        headers = {
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{port}",
        }
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=5) as response:
        return response.status, response.headers, response.read()


async def test_separate_web_app_proxies_status_and_live_arm_controls(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[sip]\nhost = \"127.0.0.1\"\nport = 5060\n"
        "[i2c]\nmock = true\n"
        "[arm]\nhome_on_start = true\n",
        encoding="utf-8",
    )
    config = AppConfig(
        sip=SIPConfig(host="127.0.0.1", port=0, rtp_port_start=0, rtp_port_end=0),
        i2c=I2CConfig(mock=True),
    )
    arm_server = RoborekaServer(config)
    await arm_server.start()
    api = ArmControlAPI(arm_server, config_path, port=0)
    api.start()
    ui = WebUIApplication(
        api_url=f"http://127.0.0.1:{api._httpd.server_port}",
        port=0,
    )
    ui.start()

    try:
        ui_port = ui._httpd.server_port
        _, headers, page = await asyncio.to_thread(_request, ui_port, "/")
        assert headers.get_content_type() == "text/html"
        assert b"Live arm control" in page
        assert b"Call action blocks" in page
        assert b"Step-by-step instructions" in page
        assert b"arm-stage-svg" in page

        _, _, status_body = await asyncio.to_thread(_request, ui_port, "/api/status")
        status = json.loads(status_body)
        assert status["active_calls"] == 0
        assert status["joints"][0]["home_angle"] == 90.0

        move_body = json.dumps({"joint": "base", "angle": 120.0}).encode()
        _, _, result_body = await asyncio.to_thread(
            _request,
            ui_port,
            "/api/arm/move",
            method="POST",
            data=move_body,
        )
        assert "Moved base" in json.loads(result_body)["message"]
        assert arm_server.arm.current_angles["base"] == pytest.approx(120.0)

        invalid_body = json.dumps({"joint": "base", "angle": 181.0}).encode()
        with pytest.raises(HTTPError) as error:
            await asyncio.to_thread(
                _request,
                ui_port,
                "/api/arm/move",
                method="POST",
                data=invalid_body,
            )
        assert error.value.code == 400

        home_body = json.dumps({}).encode()
        await asyncio.to_thread(
            _request,
            ui_port,
            "/api/arm/home",
            method="POST",
            data=home_body,
        )
        assert arm_server.arm.current_angles["base"] == pytest.approx(90.0)

        pose_body = json.dumps({"angles": {"base": 115.0, "shoulder": 105.0}}).encode()
        _, _, pose_result = await asyncio.to_thread(
            _request,
            ui_port,
            "/api/arm/pose",
            method="POST",
            data=pose_body,
        )
        assert "Moved 2 joint(s)" in json.loads(pose_result)["message"]
        assert arm_server.arm.current_angles["base"] == pytest.approx(115.0)
        assert arm_server.arm.current_angles["shoulder"] == pytest.approx(105.0)

        for bad_payload in [
            {"angles": {}},
            {"angles": {"nonexistent": 90.0}},
            {"angles": {"base": 181.0}},
            {"angles": {"base": True}},
        ]:
            with pytest.raises(HTTPError) as pose_err:
                await asyncio.to_thread(
                    _request,
                    ui_port,
                    "/api/arm/pose",
                    method="POST",
                    data=json.dumps(bad_payload).encode(),
                )
            assert pose_err.value.code == 400

        await asyncio.to_thread(
            _request,
            ui_port,
            "/api/arm/home",
            method="POST",
            data=home_body,
        )
        assert arm_server.arm.current_angles["base"] == pytest.approx(90.0)

        await asyncio.to_thread(
            _request,
            ui_port,
            "/api/arm/release",
            method="POST",
            data=home_body,
        )
        assert (
            arm_server.bus.registers[(0x40, PCA9685.ALL_LED_ON_L + 3)]
            == PCA9685.FULL_OFF_BIT
        )
    finally:
        ui.stop()
        api.stop()
        await arm_server.stop()


def test_web_ui_rejects_non_loopback_arm_api():
    with pytest.raises(ValueError, match="loopback"):
        WebUIApplication(api_url="http://192.168.1.10:8081", port=0)
