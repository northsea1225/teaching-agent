from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_endpoint() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert "Teaching Agent" in response.text
    assert "按四步推进：先录入需求，再确认约束，随后生成课件，最后导出交付。" in response.text
    assert "workflow-strip" in response.text
    assert "Step 1" in response.text
    assert "Step 2" in response.text
    assert "Step 3" in response.text
    assert "Step 4" in response.text
    assert "需求录入" in response.text
    assert "约束确认" in response.text
    assert "生成课件" in response.text
    assert "导出交付" in response.text
    assert "命中证据确认" in response.text
    assert "项目概览" in response.text
    assert "生成进度" in response.text
    assert "最近产物" in response.text
    assert "课题与范围" in response.text
    assert "这里只保留项目摘要，不展示接口原始返回。" in response.text
    assert "这里展示低保真预览或 SVG 页面，不直接展示接口返回。" in response.text
    assert "debugBadge" not in response.text
    assert "检测到兼容模式，请关闭 Edge 的 IE 模式" not in response.text
    assert "接口结果" not in response.text
    assert "jsonOutput" not in response.text
    assert "数字便利贴" in response.text
    assert "SVG 中间稿" in response.text
    assert "主题方案" in response.text
    assert "字体方案" in response.text
    assert "联网补充搜索" in response.text
    assert "先勾掉不相关资料，再确认约束" in response.text
    assert 'id="sendBtn"' in response.text
    assert 'id="uploadBtn"' in response.text
    assert 'id="evidenceBox"' in response.text
    assert 'id="refreshEvidenceBtn"' in response.text
    assert 'id="applyEvidenceBtn"' in response.text
    assert 'id="previewFrame"' in response.text
    assert 'src="/viewer"' in response.text
    assert 'type="button"' in response.text
    assert "上一页" in response.text
    assert "下一页" in response.text
    assert "SVG 缩略导航将在生成中间稿后显示" in response.text
    assert '/static/css/workbench.css?v=20260321b' in response.text
    assert '/static/js/workbench.js?v=20260321b' in response.text
    assert "/docs" in response.text
    assert "/api/health" in response.text


def test_viewer_page() -> None:
    response = client.get("/viewer")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Teaching Agent Viewer" in response.text
    assert 'id="viewerStage"' in response.text
    assert 'id="viewerHtmlFrame"' in response.text
    assert '/static/css/viewer.css?v=20260321b' in response.text
    assert '/static/js/viewer.js?v=20260321b' in response.text


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["environment"] == "development"


def test_frontend_static_assets() -> None:
    workbench_css = client.get("/static/css/workbench.css?v=20260321b")
    assert workbench_css.status_code == 200
    assert "text/css" in workbench_css.headers["content-type"]
    assert ".svg-thumb.nearby" in workbench_css.text
    assert ".svg-thumb.muted" in workbench_css.text
    assert "preview-swap" in workbench_css.text
    assert "thumbs-refresh" in workbench_css.text

    workbench_js = client.get("/static/js/workbench.js?v=20260321b")
    assert workbench_js.status_code == 200
    assert "javascript" in workbench_js.headers["content-type"]
    assert "window.__submitDemand" in workbench_js.text
    assert "window.renderPayload" in workbench_js.text
    assert '/api/evidence/selection' in workbench_js.text
    assert '/api/evidence/refresh' in workbench_js.text
    assert "split(/[；;\\\\n]/)" in workbench_js.text
    assert "需求已提交。先看确认清单，确认后再生成大纲和导出。" in workbench_js.text
    assert "viewer-empty" in workbench_js.text
    assert "viewer-html" in workbench_js.text
    assert "viewer-svg" in workbench_js.text

    viewer_css = client.get("/static/css/viewer.css?v=20260321b")
    assert viewer_css.status_code == 200
    assert "text/css" in viewer_css.headers["content-type"]
    assert ".viewer-shell" in viewer_css.text
    assert ".viewer-frame" in viewer_css.text

    viewer_js = client.get("/static/js/viewer.js?v=20260321b")
    assert viewer_js.status_code == 200
    assert "javascript" in viewer_js.headers["content-type"]
    assert "viewer-empty" in viewer_js.text
    assert "viewer-html" in viewer_js.text
    assert "viewer-svg" in viewer_js.text
    assert "data-viewer-ready" in viewer_js.text
