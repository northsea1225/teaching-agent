(function () {
  const titleNode = document.getElementById("viewerTitle");
  const metaNode = document.getElementById("viewerMeta");
  const badgeNode = document.getElementById("viewerModeBadge");
  const emptyNode = document.getElementById("viewerEmptyState");
  const stageNode = document.getElementById("viewerStage");
  const htmlFrame = document.getElementById("viewerHtmlFrame");

  function setMode(modeLabel) {
    badgeNode.textContent = modeLabel;
  }

  function showEmpty(title = "等待预览内容", meta = "工作台会把低保真预览或 SVG 中间稿发送到这里。") {
    titleNode.textContent = title;
    metaNode.textContent = meta;
    emptyNode.hidden = false;
    stageNode.hidden = true;
    htmlFrame.hidden = true;
    stageNode.innerHTML = "";
    htmlFrame.srcdoc = "";
    setMode("EMPTY");
  }

  function showHtml(payload) {
    titleNode.textContent = payload.title || "HTML Preview";
    metaNode.textContent = payload.meta || "当前正在查看低保真预览。";
    emptyNode.hidden = true;
    stageNode.hidden = true;
    htmlFrame.hidden = false;
    htmlFrame.srcdoc = payload.html_document || "";
    setMode("HTML");
  }

  function showSvg(payload) {
    titleNode.textContent = payload.title || "SVG Preview";
    metaNode.textContent = payload.meta || "当前正在查看 SVG 中间稿。";
    emptyNode.hidden = true;
    htmlFrame.hidden = true;
    stageNode.hidden = false;
    stageNode.innerHTML = payload.markup || "";
    setMode("SVG");
  }

  window.addEventListener("message", (event) => {
    const payload = event.data || {};
    if (payload.source !== "teaching-agent-workbench") {
      return;
    }

    if (payload.type === "viewer-empty") {
      showEmpty(payload.title, payload.meta);
      return;
    }

    if (payload.type === "viewer-html") {
      showHtml(payload);
      return;
    }

    if (payload.type === "viewer-svg") {
      showSvg(payload);
    }
  });

  document.body.setAttribute("data-viewer-ready", "1");
  showEmpty();
})();
