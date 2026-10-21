"""Two fixed Dorosin presets, exposed as HTTP endpoints by mcpo."""

import asyncio
import json
import os
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.fastmcp import FastMCP


UPSTREAM_URL = "https://app.api.cloud.mxchip.com:2443/mcp"
DEVICE_NAME = "多乐信除湿机"
EXPECTED_MODES = {1: "连续", 4: "舒适"}
server = FastMCP("Dorosin presets", log_level="WARNING")
_lock = asyncio.Lock()
_device_id: str | None = None


class PresetError(RuntimeError):
    """A safe, actionable error that can be returned to the HTTP caller."""


def decode_result(result: Any) -> dict[str, Any]:
    """Accept structured MCP output or its JSON text equivalent."""
    if result.isError:
        raise PresetError("mxchip MCP reported a tool error")
    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    for block in result.content:
        if getattr(block, "type", None) == "text":
            try:
                payload = json.loads(block.text)
            except (ValueError, TypeError):
                continue
            if isinstance(payload, dict):
                return payload
    raise PresetError("mxchip MCP did not return a JSON object")


async def call(session: ClientSession, name: str, arguments: dict) -> dict:
    return decode_result(await session.call_tool(name, arguments))


async def device_id(session: ClientSession) -> str:
    global _device_id
    if _device_id is None:
        payload = await call(session, "list_devices_and_scenes", {})
        devices = [
            d for d in payload.get("devices", [])
            if d.get("name") == DEVICE_NAME and d.get("category") == "DEHUMIDIFIER"
        ]
        if len(devices) != 1 or not devices[0].get("device_iot_id"):
            raise PresetError("Expected exactly one matching Dorosin dehumidifier")
        candidate = devices[0]["device_iot_id"]
        status = await read_status(session, candidate, detail="full")
        mode = next((p for p in status.get("properties", []) if p.get("key") == "mode"), {})
        modes = {item["value"]: item["label"] for item in mode.get("enum", [])}
        if not mode.get("writable") or any(modes.get(k) != v for k, v in EXPECTED_MODES.items()):
            raise PresetError("Device mode definitions differ from the verified presets")
        _device_id = candidate
    return _device_id


async def read_status(session: ClientSession, identifier: str, detail: str = "summary") -> dict:
    payload = await call(session, "get_device_status", {
        "device_iot_ids": [identifier], "detail": detail,
    })
    devices = [d for d in payload.get("devices", []) if d.get("device_iot_id") == identifier]
    if len(devices) != 1 or not devices[0].get("online"):
        raise PresetError("Dehumidifier is unavailable or offline")
    return devices[0]


def summarize(device: dict) -> dict:
    properties = {p["key"]: p for p in device.get("properties", [])}
    result = {"device": device["name"], "online": device["online"]}
    for key in ("power", "mode", "work_status", "current_humidity", "current_temperature"):
        prop = properties.get(key, {})
        result[key] = prop.get("value")
        if "value_label" in prop:
            result[key + "_label"] = prop["value_label"]
    return result


async def set_mode(mode: int, preset: str) -> dict[str, Any]:
    try:
        return await _set_mode(mode, preset)
    except ExceptionGroup as group:
        # MCP's transport wraps application errors in nested task groups.
        def find_expected(error: BaseException) -> PresetError | None:
            if isinstance(error, PresetError):
                return error
            for child in getattr(error, "exceptions", ()):
                found = find_expected(child)
                if found is not None:
                    return found
            return None
        expected = find_expected(group)
        raise PresetError(str(expected) if expected else "mxchip connection failed") from None


async def _set_mode(mode: int, preset: str) -> dict[str, Any]:
    # Serialize the complete write/readback sequence for these two endpoints.
    async with _lock:
        authorization = os.environ.get("AUTHORIZATION", "").strip()
        if not authorization:
            raise PresetError("AUTHORIZATION is required")
        async with streamablehttp_client(
            UPSTREAM_URL, headers={"Authorization": authorization},
            timeout=20, sse_read_timeout=45,
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                identifier = await device_id(session)
                before = summarize(await read_status(session, identifier))
                mode_action = {"type": "set_prop", "device_iot_id": identifier, "property": "mode", "value": mode}
                # A redundant power-on can overwrite a simultaneous mode change.
                actions = [] if before.get("power") == 1 else [{"type": "turn_on", "device_iot_id": identifier}]
                actions.append(mode_action)
                response = await call(session, "control_devices", {"actions": actions})
                results = response.get("results", [])
                if len(results) != len(actions) or not all(r.get("success") is True for r in results):
                    raise PresetError("mxchip did not accept every control action; state may be partially changed")
                for attempt in range(10):
                    state = summarize(await read_status(session, identifier))
                    if state.get("power") == 1 and state.get("mode") == mode:
                        return {"success": True, "confirmed": True, "preset": preset, **state}
                    if attempt == 2 and state.get("power") == 1:
                        # Reapply only mode after power-on if the combined write was overwritten.
                        retried = await call(session, "control_devices", {"actions": [mode_action]})
                        retry_results = retried.get("results", [])
                        if len(retry_results) != 1 or retry_results[0].get("success") is not True:
                            raise PresetError("mxchip did not accept the mode retry")
                    if attempt < 9:
                        await asyncio.sleep(1)
                raise PresetError("Control was accepted, but device readback did not confirm the requested mode")


@server.tool()
async def continuous_drying() -> dict[str, Any]:
    """开启多乐信除湿机并设为连续干衣：设备连续模式 mode=1，回读确认后返回。"""
    return await set_mode(1, "continuous_drying")


@server.tool()
async def comfort_sleep() -> dict[str, Any]:
    """开启多乐信除湿机并设为舒适睡眠：使用设备舒适模式 mode=4，无独立睡眠档。"""
    return await set_mode(4, "comfort_sleep")


if __name__ == "__main__":
    server.run(transport="stdio")
