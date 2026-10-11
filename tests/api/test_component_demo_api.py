import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import create_app
from videoagents.contracts import Asset
from videoagents.storage.repository import dumps, fingerprint, now


def client_with_session(tmp_path):
    app = create_app(tmp_path / "runtime", tmp_path / "project")
    client = TestClient(app)
    client.__enter__()
    token = client.get("/api/session").json()["csrf_token"]
    client.headers["X-CSRF-Token"] = token
    return client


def create_job(client):
    response = client.post("/api/jobs", json={
        "topic": "组件套样片测试",
        "creative_direction": "只导入素材后生成组件套样片。",
        "target_seconds": 30,
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "usage": "personal",
        "platform": "抖音",
    })
    assert response.status_code == 201
    return response.json()


def attach_visual_asset(repo, service, job, *, asset_id="asset-demo-1", role="illustration", source_url="", metadata=None):
    current = repo.get_job(job["job_id"])
    folder = repo.root / "jobs" / current.job_id / "assets"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{asset_id}.png"
    path.write_bytes(b"unit image bytes")
    artifact = service.register_artifact(current, path, "asset", "image/png")
    asset = Asset(
        asset_id=asset_id,
        name=f"{asset_id}.png",
        role=role,
        mime_type="image/png",
        size_bytes=artifact.size_bytes,
        sha256=artifact.sha256,
        source_url=source_url,
        artifact_id=artifact.artifact_id,
        url=artifact.url,
        timeline_src=f"videoagents/{current.job_id}/assets/{asset_id}.png",
    )
    updated = repo.add_asset(current.job_id, asset, artifact, metadata or {"origin": "unit", "width": 1080, "height": 1920})
    return updated, asset


def attach_video_asset(repo, service, job, *, metadata=None):
    current = repo.get_job(job["job_id"])
    folder = repo.root / "jobs" / current.job_id / "assets"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "unit-screen.mp4"
    path.write_bytes(b"unit video bytes")
    artifact = service.register_artifact(current, path, "asset", "video/mp4")
    asset = Asset(
        asset_id="asset-video-1",
        name="unit-screen.mp4",
        role="illustration",
        mime_type="video/mp4",
        size_bytes=artifact.size_bytes,
        sha256=artifact.sha256,
        artifact_id=artifact.artifact_id,
        url=artifact.url,
        timeline_src=f"videoagents/{current.job_id}/assets/unit-screen.mp4",
    )
    updated = repo.add_asset(current.job_id, asset, artifact, metadata or {"origin": "unit", "duration_seconds": 10, "width": 540, "height": 960})
    return updated, asset


def tutorial_steps(frames=300):
    return [
        {"start_frame": 0, "end_frame": 90, "instruction": "输入提醒事项", "target": {"x": 0.12, "y": 0.28, "width": 0.76, "height": 0.12}},
        {"start_frame": 90, "end_frame": 180, "instruction": "点击保存提醒", "target": {"x": 0.18, "y": 0.64, "width": 0.64, "height": 0.10}},
        {"start_frame": 180, "end_frame": frames, "instruction": "列表出现结果", "target": {"x": 0.10, "y": 0.38, "width": 0.80, "height": 0.16}},
    ]


def focus_steps(frames=300):
    return [
        {"start_frame": 0, "end_frame": 120, "instruction": "先看输入框", "target": {"x": 0.10, "y": 0.24, "width": 0.80, "height": 0.14}},
        {"start_frame": 120, "end_frame": 210, "instruction": "再看保存按钮", "target": {"x": 0.18, "y": 0.62, "width": 0.64, "height": 0.10}},
        {"start_frame": 210, "end_frame": frames, "instruction": "最后看结果", "target": {"x": 0.12, "y": 0.38, "width": 0.76, "height": 0.18}},
    ]


def b_content(set_id="B01"):
    values = {
        "B01": {"title": "先问一个问题", "body": "这件事到底是谁在聊天，谁在收钱。", "takeaway": "先核实身份"},
        "B02": {"title": "什么是AI陪聊", "body": "AI负责多数文字互动，真人接住机器做不好的环节。", "takeaway": "分清机器和真人"},
        "B03": {"title": "两种风险不同", "body": "同样是聊天，风险来自不同节点。", "takeaway": "看清转折点", "items": ["AI文字陪聊", "真人视频接管"]},
        "B04": {"title": "先看代价", "body": "演示数字只用来测试计数器，不代表真实统计。", "takeaway": "数字要问口径", "metric": {"label": "演示费用", "value": "399元", "detail": "演示数字"}},
        "B05": {"title": "三步判断", "body": "先确认身份，再看收费动作，最后问家人。", "takeaway": "别急着转账", "items": ["确认对方身份", "停下充值动作", "找家人复核"]},
        "B06": {"title": "给家人的提醒", "body": "看到陌生陪聊和视频请求，先把流程停下来。", "takeaway": "先停再核实", "items": ["不私下转账", "截图发给家人", "必要时报警"]},
    }
    return values[set_id]






def expanded_content(set_id):
    path = Path("tests/fixtures/component-set-expanded-content.json")
    content = json.loads(path.read_text(encoding="utf-8"))
    return content[set_id]


def material_rich_content(set_id):
    path = Path("tests/fixtures/component-set-material-rich-content.json")
    content = json.loads(path.read_text(encoding="utf-8"))
    return content[set_id]


def b_rich_content(set_id="B04"):
    values = {
        "B01": {"title": "先问谁在聊", "body": "三条线索一起看，别只听对方解释。", "takeaway": "先核实身份", "items": ["账号是谁", "谁在收费", "谁要视频"], "metric": {"label": "演示线索", "value": "3项", "detail": "演示数字"}},
        "B04": {"title": "费用先拆开", "body": "总数必须来自三项累加，方便看出口径。", "takeaway": "数字要问口径", "metric": {"label": "演示合计", "value": "399元", "detail": "演示数字"}, "numeric_items": ["会员:199元", "礼物:100元", "视频:100元"]},
    }
    return values[set_id]


def insert_command(repo, job_id, payload, command_id):
    with repo.connection(immediate=True) as db:
        db.execute(
            "INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
            "VALUES(?,?,?,?,?,'DONE',?)",
            (command_id, job_id, payload["idempotency_key"], dumps(payload), fingerprint(payload), now()),
        )


def insert_raw_command(repo, job_id, payload_text, command_id, idempotency_key):
    with repo.connection(immediate=True) as db:
        db.execute(
            "INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
            "VALUES(?,?,?,?,?,'DONE',?)",
            (command_id, job_id, idempotency_key, payload_text, fingerprint(payload_text), now()),
        )


def patch_brief_revision(client, current, creative_direction="保存新版本后再次出样片"):
    brief = current.brief.model_dump()
    brief["creative_direction"] = creative_direction
    response = client.patch(f"/api/jobs/{current.job_id}/draft", json={
        "base_revision": current.revision,
        "brief": brief,
    })
    assert response.status_code == 200, response.text
    return client.app.state.repository.get_job(current.job_id)


def queued_payload(repo, job_id, key="component-demo-key"):
    with repo.connection() as db:
        row = db.execute(
            "SELECT payload,status FROM commands WHERE job_id=? AND idempotency_key=?",
            (job_id, key),
        ).fetchone()
    assert row is not None
    return json.loads(row["payload"]), row["status"]


def test_component_demo_endpoint_queues_formal_payload_and_is_idempotent(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)

        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A01",
            "asset_id": asset.asset_id,
        }
        first = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)
        assert first.status_code == 202, first.text
        assert first.json()["status"] == "QUEUED"

        second = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)
        assert second.status_code == 202

        payload, status = queued_payload(repo, current.job_id)
        assert status == "PENDING"
        assert payload == {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "action": "component_demo",
            "component_demo": {
                "set_id": "A01",
                "asset_id": asset.asset_id,
                "duration_seconds": 10,
            },
        }
        with repo.connection() as db:
            assert db.execute(
                "SELECT COUNT(*) FROM commands WHERE job_id=? AND idempotency_key=?",
                (current.job_id, "component-demo-key"),
            ).fetchone()[0] == 1
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize("set_id", ["B01", "B02", "B03", "B04", "B05", "B06"])
def test_component_demo_endpoint_queues_no_material_b_payload(tmp_path, set_id):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        current = repo.get_job(job["job_id"])
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": set_id,
            "duration_seconds": 8,
            "content": b_content(set_id),
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, current.job_id)
        assert payload == {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "action": "component_demo",
            "component_demo": {
                "set_id": set_id,
                "duration_seconds": 8.0,
                "content": b_content(set_id),
            },
        }
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_asset_for_no_material_b_set(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B01",
            "asset_id": asset.asset_id,
            "content": b_content("B01"),
        })

        assert response.status_code == 422
        assert "不接受 asset_id" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_no_material_b_when_job_has_assets(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, _ = attach_visual_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B02",
            "content": b_content("B02"),
        })

        assert response.status_code == 409
        assert "空素材草稿" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize(("body_patch", "expected"), [
    ({"content": None}, "必须提供 content"),
    ({"content": {**b_content("B01"), "items": ["多余", "参数"]}}, "只接受"),
    ({"set_id": "B04", "content": {**b_content("B04"), "metric": {"label": "   ", "value": "399元", "detail": "演示数字"}}}, "不能为空"),
    ({"set_id": "B04", "content": {**b_content("B04"), "metric": {"label": "演示比例", "value": "80%", "detail": "演示数字"}}}, "整数加 1 到 2 个汉字单位"),
    ({"set_id": "B04", "content": {**b_content("B04"), "metric": {"label": "演示小数", "value": "3.5元", "detail": "演示数字"}}}, "整数加 1 到 2 个汉字单位"),
    ({"set_id": "B04", "content": {**b_content("B04"), "metric": {"label": "演示数字", "value": "３９９元", "detail": "演示数字"}}}, "整数加 1 到 2 个汉字单位"),
    ({"set_id": "B06", "content": {**b_content("B06"), "items": ["一" * 32, "二" * 32, "三" * 32]}}, "合计不能超过 64 字"),
])
def test_component_demo_endpoint_rejects_invalid_no_material_b_content(tmp_path, body_patch, expected):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        current = repo.get_job(job["job_id"])
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B01",
            "content": b_content("B01"),
        }
        body.update(body_patch)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 422
        assert expected in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_still_requires_asset_for_material_sets(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        current = repo.get_job(job["job_id"])

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A01",
        })

        assert response.status_code == 422
        assert "asset_id" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_queues_guided_a02_steps(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job)
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A02",
            "asset_id": asset.asset_id,
            "duration_seconds": 10,
            "tutorial_steps": tutorial_steps(),
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, current.job_id)
        assert payload["component_demo"] == {
            "set_id": "A02",
            "asset_id": asset.asset_id,
            "duration_seconds": 10.0,
            "tutorial_steps": tutorial_steps(),
        }
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_queues_focus_steps_for_material_sets(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job)
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A03",
            "asset_id": asset.asset_id,
            "duration_seconds": 10,
            "focus_steps": focus_steps(),
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, current.job_id)
        assert payload["component_demo"] == {
            "set_id": "A03",
            "asset_id": asset.asset_id,
            "duration_seconds": 10.0,
            "focus_steps": focus_steps(),
        }
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_focus_steps_for_a02(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A02",
            "asset_id": asset.asset_id,
            "duration_seconds": 10,
            "focus_steps": focus_steps(),
        })

        assert response.status_code == 422
        assert "A03-A06" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_mixed_tutorial_and_focus_steps(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A02",
            "asset_id": asset.asset_id,
            "duration_seconds": 10,
            "tutorial_steps": tutorial_steps(),
            "focus_steps": focus_steps(),
        })

        assert response.status_code == 422
        assert "不能同时提供" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_focus_asset_without_dimensions(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job, metadata={"origin": "unit"})

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A04",
            "asset_id": asset.asset_id,
            "duration_seconds": 10,
            "focus_steps": focus_steps(),
        })

        assert response.status_code == 409
        assert "尺寸元数据" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_focus_a05_without_evidence_source(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A05",
            "asset_id": asset.asset_id,
            "duration_seconds": 10,
            "focus_steps": focus_steps(),
        })

        assert response.status_code == 409
        assert "evidence" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_guided_steps_for_other_sets(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A03",
            "asset_id": asset.asset_id,
            "duration_seconds": 10,
            "tutorial_steps": tutorial_steps(),
        })

        assert response.status_code == 422
        assert "只允许用于 A02" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_guided_a02_image_asset(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A02",
            "asset_id": asset.asset_id,
            "duration_seconds": 10,
            "tutorial_steps": tutorial_steps(),
        })

        assert response.status_code == 409
        assert "MP4" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize("set_id", ["A00", "C01"])
def test_component_demo_endpoint_rejects_unknown_set_ids(tmp_path, set_id):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": set_id,
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 422
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize("set_id", ["A07", "A08", "A10", "A11", "A12"])
def test_component_demo_endpoint_queues_material_rich_image_payload(tmp_path, set_id):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": set_id,
            "asset_id": asset.asset_id,
            "duration_seconds": 15,
            "composition": "rich",
            "content": material_rich_content(set_id),
        })

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, current.job_id)
        assert payload["component_demo"] == {
            "set_id": set_id,
            "asset_id": asset.asset_id,
            "duration_seconds": 15.0,
            "composition": "rich",
            "content": material_rich_content(set_id),
        }
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_queues_material_rich_a09_video_payload(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job, metadata={
            "origin": "unit",
            "duration_seconds": 371 / 30,
            "frame_rate": 30.0,
            "width": 720,
            "height": 1440,
        })
        steps = [
            {"start_frame": 0, "end_frame": 115, "instruction": "输入事项", "target": {"x": 0.10, "y": 0.18, "width": 0.80, "height": 0.16}},
            {"start_frame": 115, "end_frame": 179, "instruction": "点保存", "target": {"x": 0.18, "y": 0.60, "width": 0.64, "height": 0.12}},
            {"start_frame": 179, "end_frame": 371, "instruction": "查看列表", "target": {"x": 0.10, "y": 0.34, "width": 0.80, "height": 0.24}},
        ]

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A09",
            "asset_id": asset.asset_id,
            "duration_seconds": 371 / 30,
            "composition": "rich",
            "content": material_rich_content("A09"),
            "focus_steps": steps,
        })

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, current.job_id)
        assert payload["component_demo"]["duration_seconds"] == 371 / 30
        assert payload["component_demo"]["focus_steps"] == steps
        assert payload["component_demo"]["content"] == material_rich_content("A09")
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_material_rich_a09_missing_focus_steps(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job, metadata={
            "origin": "unit",
            "duration_seconds": 371 / 30,
            "frame_rate": 30.0,
            "width": 720,
            "height": 1440,
        })

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A09",
            "asset_id": asset.asset_id,
            "duration_seconds": 371 / 30,
            "composition": "rich",
            "content": material_rich_content("A09"),
        })

        assert response.status_code == 422
        assert "必须提供 focus_steps" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize(("patch", "expected"), [
    ({"composition": "basic"}, "只支持 rich"),
    ({"content": {**material_rich_content("A07"), "metric": {"label": "多余", "value": "3项"}}}, "不接受 metric"),
    ({"content": {**material_rich_content("A07"), "items": ["一项", "两项"]}}, "exactly 3"),
])
def test_component_demo_endpoint_rejects_invalid_material_rich_content(tmp_path, patch, expected):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A07",
            "asset_id": asset.asset_id,
            "duration_seconds": 15,
            "composition": "rich",
            "content": material_rich_content("A07"),
        }
        body.update(patch)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 422
        assert expected in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_material_rich_wrong_asset_type(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A07",
            "asset_id": asset.asset_id,
            "duration_seconds": 15,
            "composition": "rich",
            "content": material_rich_content("A07"),
        })

        assert response.status_code == 409
        assert "图片素材" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_a09_wrong_frame_count(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_video_asset(repo, service, job, metadata={
            "origin": "unit",
            "duration_seconds": 371 / 30,
            "frame_count": 370,
            "frame_rate": 30.0,
            "width": 720,
            "height": 1440,
        })
        steps = [
            {"start_frame": 0, "end_frame": 115, "instruction": "输入事项", "target": {"x": 0.10, "y": 0.18, "width": 0.80, "height": 0.16}},
            {"start_frame": 115, "end_frame": 179, "instruction": "点保存", "target": {"x": 0.18, "y": 0.60, "width": 0.64, "height": 0.12}},
            {"start_frame": 179, "end_frame": 371, "instruction": "查看列表", "target": {"x": 0.10, "y": 0.34, "width": 0.80, "height": 0.24}},
        ]

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A09",
            "asset_id": asset.asset_id,
            "duration_seconds": 371 / 30,
            "composition": "rich",
            "content": material_rich_content("A09"),
            "focus_steps": steps,
        })

        assert response.status_code == 409
        assert "frame_count" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_existing_production_history(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        payload = {"base_revision": current.revision, "action": "produce", "idempotency_key": "old-production"}
        insert_command(repo, current.job_id, payload, "a" * 32)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A02",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 409
        assert "生产或恢复命令历史" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_non_object_command_history(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        insert_raw_command(repo, current.job_id, "[]", "a" * 32, "raw-history")

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A02",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 409
        assert "无法识别" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_pending_or_non_material_jobs(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        repo.update_job(
            current.job_id,
            current.revision,
            pending_input={"kind": "input", "stage": "materials", "pending_token": "x" * 16},
        )

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A03",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 409
        assert "无待办" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_missing_asset(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, _ = attach_visual_asset(repo, service, job)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A04",
            "asset_id": "missing-asset",
        })

        assert response.status_code == 409
        assert "素材不存在" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_allows_pure_older_component_demo_history_after_new_revision(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        old_payload = {
            "base_revision": current.revision,
            "idempotency_key": "old-component-demo",
            "action": "component_demo",
            "component_demo": {"set_id": "A01", "asset_id": asset.asset_id, "duration_seconds": 10},
        }
        insert_command(repo, current.job_id, old_payload, "b" * 32)
        revised = patch_brief_revision(client, current)

        response = client.post(f"/api/jobs/{revised.job_id}/component-demo", json={
            "base_revision": revised.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A02",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, revised.job_id)
        assert payload["base_revision"] == revised.revision
        assert payload["action"] == "component_demo"
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_allows_older_component_demo_render_recovery_after_new_revision(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        old_command_id = "e" * 32
        old_payload = {
            "base_revision": current.revision,
            "idempotency_key": "old-component-demo",
            "action": "component_demo",
            "component_demo": {"set_id": "A01", "asset_id": asset.asset_id, "duration_seconds": 10},
        }
        insert_command(repo, current.job_id, old_payload, old_command_id)
        insert_command(repo, current.job_id, {
            "base_revision": current.revision,
            "idempotency_key": "old-component-demo-recovery",
            "action": "resume",
            "decision": "confirm",
            "pending_token": "p" * 16,
            "pending_input": {
                "kind": "input",
                "stage": "director",
                "retry_node": "director_demo",
                "thread_id": f"job:{current.job_id}:run:{old_command_id}",
            },
        }, "f" * 32)
        revised = patch_brief_revision(client, current)

        response = client.post(f"/api/jobs/{revised.job_id}/component-demo", json={
            "base_revision": revised.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A03",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, revised.job_id)
        assert payload["base_revision"] == revised.revision
        assert payload["action"] == "component_demo"
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_older_arbitrary_resume_after_new_revision(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        insert_command(repo, current.job_id, {
            "base_revision": current.revision,
            "idempotency_key": "old-arbitrary-resume",
            "action": "resume",
            "decision": "confirm",
            "pending_token": "p" * 16,
            "pending_input": {
                "kind": "input",
                "stage": "render",
                "retry_node": "render",
                "thread_id": f"job:{current.job_id}:run:{'a' * 32}",
            },
        }, "f" * 32)
        revised = patch_brief_revision(client, current)

        response = client.post(f"/api/jobs/{revised.job_id}/component-demo", json={
            "base_revision": revised.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A03",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 409
        assert "生产或恢复命令历史" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_component_demo_recovery_with_mismatched_revision(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        old_command_id = "e" * 32
        insert_command(repo, current.job_id, {
            "base_revision": current.revision,
            "idempotency_key": "old-component-demo",
            "action": "component_demo",
            "component_demo": {"set_id": "A01", "asset_id": asset.asset_id, "duration_seconds": 10},
        }, old_command_id)
        revised = patch_brief_revision(client, current)
        insert_command(repo, current.job_id, {
            "base_revision": revised.revision,
            "idempotency_key": "mismatched-component-demo-recovery",
            "action": "resume",
            "decision": "confirm",
            "pending_token": "p" * 16,
            "pending_input": {
                "kind": "input",
                "stage": "director",
                "retry_node": "director_demo",
                "thread_id": f"job:{current.job_id}:run:{old_command_id}",
            },
        }, "f" * 32)

        response = client.post(f"/api/jobs/{revised.job_id}/component-demo", json={
            "base_revision": revised.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A03",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 409
        assert "生产或恢复命令历史" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_same_revision_component_demo_history(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        old_payload = {
            "base_revision": current.revision,
            "idempotency_key": "old-component-demo",
            "action": "component_demo",
            "component_demo": {"set_id": "A01", "asset_id": asset.asset_id, "duration_seconds": 10},
        }
        insert_command(repo, current.job_id, old_payload, "c" * 32)

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json={
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A02",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 409
        assert "当前版本已有组件套样片命令" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_older_production_history_after_new_revision(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        service = client.app.state.service
        current, asset = attach_visual_asset(repo, service, job)
        insert_command(repo, current.job_id, {
            "base_revision": current.revision,
            "action": "produce",
            "idempotency_key": "old-production",
        }, "d" * 32)
        revised = patch_brief_revision(client, current)

        response = client.post(f"/api/jobs/{revised.job_id}/component-demo", json={
            "base_revision": revised.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "A03",
            "asset_id": asset.asset_id,
        })

        assert response.status_code == 409
        assert "生产或恢复命令历史" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_queues_rich_no_material_payload(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        current = repo.get_job(job["job_id"])
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B01",
            "duration_seconds": 15,
            "composition": "rich",
            "content": b_rich_content("B01"),
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, current.job_id)
        assert payload["component_demo"] == {
            "set_id": "B01",
            "duration_seconds": 15,
            "composition": "rich",
            "content": b_rich_content("B01"),
        }
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_rich_b04_bad_sum(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        current = client.app.state.repository.get_job(job["job_id"])
        content = {**b_rich_content("B04"), "metric": {"label": "演示合计", "value": "400元", "detail": "演示数字"}}
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B04",
            "duration_seconds": 16,
            "composition": "rich",
            "content": content,
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 422
        assert "同单位求和" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_rich_short_duration(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        current = client.app.state.repository.get_job(job["job_id"])
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B01",
            "duration_seconds": 10,
            "composition": "rich",
            "content": b_rich_content("B01"),
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 422
        assert "至少 12 秒" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_queues_expanded_rich_payload(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        current = repo.get_job(job["job_id"])
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B18",
            "duration_seconds": 18,
            "composition": "rich",
            "content": expanded_content("B18"),
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 202, response.text
        payload, _ = queued_payload(repo, current.job_id)
        assert payload["component_demo"] == {
            "set_id": "B18",
            "duration_seconds": 18,
            "composition": "rich",
            "content": expanded_content("B18"),
        }
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_expanded_basic_payload(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        current = client.app.state.repository.get_job(job["job_id"])
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B07",
            "duration_seconds": 18,
            "composition": "basic",
            "content": expanded_content("B07"),
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 422
        assert "只支持 rich" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)


def test_component_demo_endpoint_rejects_expanded_wrong_numeric_difference(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        current = client.app.state.repository.get_job(job["job_id"])
        content = {**expanded_content("B09"), "metric": {"label": "多出的核对动作", "value": "2步", "detail": "2步-1步"}}
        body = {
            "base_revision": current.revision,
            "idempotency_key": "component-demo-key",
            "set_id": "B09",
            "duration_seconds": 18,
            "composition": "rich",
            "content": content,
        }

        response = client.post(f"/api/jobs/{current.job_id}/component-demo", json=body)

        assert response.status_code == 422
        assert "同单位差值" in response.json()["detail"]
    finally:
        client.__exit__(None, None, None)
