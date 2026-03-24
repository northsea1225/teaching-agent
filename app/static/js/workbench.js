    window.__submitDemand = async function() {
      const statusBox = document.getElementById("statusBox");
      const titleInput = document.getElementById("title");
      const contentInput = document.getElementById("content");
      const sessionTag = document.getElementById("sessionTag");
      const webSearchToggle = document.getElementById("webSearchToggle");
      const content = contentInput ? contentInput.value.trim() : "";
      const title = titleInput && titleInput.value.trim() ? titleInput.value.trim() : "Untitled Session";
      if (!content) {
        if (statusBox) {
          statusBox.textContent = "请先输入教师需求。";
        }
        return;
      }
      if (statusBox) {
        statusBox.textContent = "正在提交需求...";
      }
      try {
        const response = await fetch("/api/chat/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: window.__bootstrapSessionId || null,
            title,
            content,
            use_web_search: Boolean(webSearchToggle && webSearchToggle.checked),
          }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || "Request failed");
        }
        const session =
          payload && payload.session
            ? payload.session
            : payload && payload.session_id
              ? { session_id: payload.session_id }
              : null;
        if (session && session.session_id) {
          window.__bootstrapSessionId = session.session_id;
          if (sessionTag) {
            sessionTag.textContent = `Session: ${session.session_id}`;
          }
        }
        window.__bootstrapPayload = payload;
        if (statusBox) {
          statusBox.textContent = "需求已提交。先看确认清单，确认后再生成大纲和导出。";
        }
      } catch (error) {
        if (statusBox) {
          statusBox.textContent = `提交失败：${error.message}`;
        }
      }
    };

    window.addEventListener("error", (event) => {
      const box = document.getElementById("statusBox");
      const message = `JS错误：${event.message}`;
      document.body.setAttribute("data-front-error", event.message || "unknown");
      if (box) {
        box.textContent = message;
      }
    });

    const UI_THEME_PRESETS = {
      academy: {
        bg: "#edf3f8",
        panel: "#ffffff",
        text: "#16212b",
        muted: "#58697a",
        line: "#d6e0ea",
        brand: "#123b63",
        brandSoft: "#dceaf8",
        surfaceSubtle: "#f5f9fc",
        pageGlow: "rgba(18, 59, 99, 0.16)",
        pageGlowSoft: "rgba(220, 234, 248, 0.72)",
        panelShadow: "0 14px 34px rgba(27, 53, 76, 0.08)",
      },
      studio: {
        bg: "#f7efe9",
        panel: "#fffaf6",
        text: "#2a1d16",
        muted: "#7a6558",
        line: "#ead7ca",
        brand: "#8a2c0d",
        brandSoft: "#fde6d8",
        surfaceSubtle: "#fbf1ea",
        pageGlow: "rgba(138, 44, 13, 0.18)",
        pageGlowSoft: "rgba(253, 230, 216, 0.78)",
        panelShadow: "0 16px 36px rgba(138, 44, 13, 0.10)",
      },
      field: {
        bg: "#edf6f0",
        panel: "#fbfefc",
        text: "#13241b",
        muted: "#5d7768",
        line: "#d3e5da",
        brand: "#166534",
        brandSoft: "#d7f0df",
        surfaceSubtle: "#f1f9f4",
        pageGlow: "rgba(22, 101, 52, 0.16)",
        pageGlowSoft: "rgba(215, 240, 223, 0.78)",
        panelShadow: "0 14px 34px rgba(22, 101, 52, 0.10)",
      },
      briefing: {
        bg: "#edf1f6",
        panel: "#fdfefe",
        text: "#111b2a",
        muted: "#5b687a",
        line: "#d6deea",
        brand: "#0f172a",
        brandSoft: "#e2e8f0",
        surfaceSubtle: "#f4f7fb",
        pageGlow: "rgba(15, 23, 42, 0.18)",
        pageGlowSoft: "rgba(226, 232, 240, 0.78)",
        panelShadow: "0 16px 34px rgba(15, 23, 42, 0.10)",
      },
    };
    const DEFAULT_UI_THEME_ID = "academy";

    const state = {
      sessionId: null,
      lastPayload: null,
      svgDeck: null,
      svgSlideIndex: 0,
      previewMode: "empty",
      uiThemeId: DEFAULT_UI_THEME_ID,
      viewerPayload: null,
    };

    const statusBox = document.getElementById("statusBox");
    const previewFrame = document.getElementById("previewFrame");
    const sessionTag = document.getElementById("sessionTag");
    const stageTag = document.getElementById("stageTag");
    const workspaceTag = document.getElementById("workspaceTag");
    const confirmationBox = document.getElementById("confirmationBox");
    const evidenceBox = document.getElementById("evidenceBox");
    const qualityBox = document.getElementById("qualityBox");
    const overviewBadge = document.getElementById("overviewBadge");
    const lessonSummaryTitle = document.getElementById("lessonSummaryTitle");
    const lessonSummaryMeta = document.getElementById("lessonSummaryMeta");
    const progressSummary = document.getElementById("progressSummary");
    const retrievalSummary = document.getElementById("retrievalSummary");
    const artifactSummary = document.getElementById("artifactSummary");
    const nextActionBox = document.getElementById("nextActionBox");
    const artifactDocxChip = document.getElementById("artifactDocxChip");
    const artifactPptxChip = document.getElementById("artifactPptxChip");
    const downloadLink = document.getElementById("downloadLink");
    const downloadPptxLink = document.getElementById("downloadPptxLink");
    const slideBoard = document.getElementById("slideBoard");
    const svgPrevBtn = document.getElementById("svgPrevBtn");
    const svgNextBtn = document.getElementById("svgNextBtn");
    const svgPageLabel = document.getElementById("svgPageLabel");
    const svgThumbStrip = document.getElementById("svgThumbStrip");
    const themeSelect = document.getElementById("themeSelect");
    const fontSelect = document.getElementById("fontSelect");
    const webSearchToggle = document.getElementById("webSearchToggle");
    const sendBtn = document.getElementById("sendBtn");
    const refreshEvidenceBtn = document.getElementById("refreshEvidenceBtn");
    const applyEvidenceBtn = document.getElementById("applyEvidenceBtn");
    const outlineBtn = document.getElementById("outlineBtn");
    const planBtn = document.getElementById("planBtn");
    const previewBtn = document.getElementById("previewBtn");
    const svgBtn = document.getElementById("svgBtn");
    const exportBtn = document.getElementById("exportBtn");
    const exportPptxBtn = document.getElementById("exportPptxBtn");
    const addSlideBtn = document.getElementById("addSlideBtn");
    const stepIntakeCard = document.getElementById("stepIntakeCard");
    const stepConfirmCard = document.getElementById("stepConfirmCard");
    const stepGenerateCard = document.getElementById("stepGenerateCard");
    const stepExportCard = document.getElementById("stepExportCard");
    const stepIntakeBadge = document.getElementById("stepIntakeBadge");
    const stepConfirmBadge = document.getElementById("stepConfirmBadge");
    const stepGenerateBadge = document.getElementById("stepGenerateBadge");
    const stepExportBadge = document.getElementById("stepExportBadge");
    const intakeStateBadge = document.getElementById("intakeStateBadge");
    const confirmStateBadge = document.getElementById("confirmStateBadge");
    const generateStateBadge = document.getElementById("generateStateBadge");
    const exportStateBadge = document.getElementById("exportStateBadge");
    const STEP_STATE_LABELS = {
      pending: "待开始",
      active: "进行中",
      done: "已完成",
    };

    function setStatus(message) {
      statusBox.textContent = message;
    }

    function webSearchEnabled() {
      return Boolean(webSearchToggle && webSearchToggle.checked);
    }

    function escapeHtml(value) {
      return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function getUiTheme(themeId = state.uiThemeId) {
      return UI_THEME_PRESETS[themeId] || UI_THEME_PRESETS[DEFAULT_UI_THEME_ID];
    }

    function restartAnimation(node, className, timeout = 340) {
      if (!node) {
        return;
      }
      node.classList.remove(className);
      void node.offsetWidth;
      node.classList.add(className);
      window.setTimeout(() => node.classList.remove(className), timeout);
    }

    function animatePreviewSwap() {
      restartAnimation(previewFrame, "preview-swap", 320);
    }

    function animateThumbStrip() {
      if (!svgThumbStrip.querySelector(".svg-thumb")) {
        return;
      }
      restartAnimation(svgThumbStrip, "thumbs-refresh", 460);
    }

    function postViewerMessage(message) {
      state.viewerPayload = {
        source: "teaching-agent-workbench",
        ...message,
      };
      if (previewFrame && previewFrame.contentWindow) {
        previewFrame.contentWindow.postMessage(state.viewerPayload, window.location.origin);
      }
      animatePreviewSwap();
    }

    previewFrame.addEventListener("load", () => {
      if (state.viewerPayload && previewFrame.contentWindow) {
        previewFrame.contentWindow.postMessage(state.viewerPayload, window.location.origin);
      }
    });

    function applyUiTheme(themeId) {
      const resolvedThemeId = UI_THEME_PRESETS[themeId] ? themeId : DEFAULT_UI_THEME_ID;
      const theme = UI_THEME_PRESETS[resolvedThemeId];
      state.uiThemeId = resolvedThemeId;
      const rootStyle = document.documentElement.style;
      rootStyle.setProperty("--bg", theme.bg);
      rootStyle.setProperty("--panel", theme.panel);
      rootStyle.setProperty("--text", theme.text);
      rootStyle.setProperty("--muted", theme.muted);
      rootStyle.setProperty("--line", theme.line);
      rootStyle.setProperty("--brand", theme.brand);
      rootStyle.setProperty("--brand-soft", theme.brandSoft);
      rootStyle.setProperty("--surface-subtle", theme.surfaceSubtle);
      rootStyle.setProperty("--page-glow", theme.pageGlow);
      rootStyle.setProperty("--page-glow-soft", theme.pageGlowSoft);
      rootStyle.setProperty("--panel-shadow", theme.panelShadow);
    }

    function clearPreviewFrame() {
      state.previewMode = "empty";
      postViewerMessage({
        type: "viewer-empty",
        title: "等待预览内容",
        meta: "工作台会把低保真预览或 SVG 中间稿发送到这里。",
      });
      updateSvgNav();
    }

    function syncSvgControls(source) {
      if (!source) {
        return;
      }
      const themeId = source.theme_id || source.svg_theme_id;
      const fontPreset = source.font_preset || source.svg_font_preset;
      if (themeId && [...themeSelect.options].some((option) => option.value === themeId)) {
        themeSelect.value = themeId;
      }
      if (fontPreset && [...fontSelect.options].some((option) => option.value === fontPreset)) {
        fontSelect.value = fontPreset;
      }
      if (typeof source.web_search_enabled === "boolean" && webSearchToggle) {
        webSearchToggle.checked = source.web_search_enabled;
      }
      applyUiTheme(themeId || themeSelect.value);
    }

    function renderSvgThumbnails() {
      const slides = state.svgDeck && state.svgDeck.slides ? state.svgDeck.slides : [];
      if (!slides.length) {
        svgThumbStrip.innerHTML = '<div class="empty-board">SVG 缩略导航将在生成中间稿后显示。</div>';
        return;
      }

      function extractCitationPreview(slide) {
        if (!slide || !slide.markup) {
          return [];
        }
        try {
          const parser = new DOMParser();
          const doc = parser.parseFromString(slide.markup, "image/svg+xml");
          const panel = doc.querySelector('g[data-role="citation-panel"]');
          if (!panel) {
            return [];
          }
          return Array.from(panel.querySelectorAll("text"))
            .map((node) => (node.textContent || "").trim())
            .filter(Boolean)
            .slice(1, 4);
        } catch (error) {
          return [];
        }
      }

      const thumbHtml = slides.map((slide, index) => {
        const distance = Math.abs(index - state.svgSlideIndex);
        const thumbState = index === state.svgSlideIndex ? "active" : distance === 1 ? "nearby" : "muted";
        const accentColor = escapeHtml(slide.accent_color || "#123b63");
        const softColor = escapeHtml(slide.soft_color || "#eef5fb");
        const citations = extractCitationPreview(slide);
        const citationsHtml = citations.length
          ? `
            <div class="svg-thumb-citations">
              <span class="svg-thumb-ref-label" style="background:${accentColor};">References</span>
              ${citations.map((item) => `
                <span
                  class="svg-thumb-ref-chip"
                  style="background:${softColor}; color:${accentColor}; border-color:${accentColor};"
                >${escapeHtml(item)}</span>
              `).join("")}
            </div>
          `
          : "";

        return `
          <button
            type="button"
            class="svg-thumb ${thumbState}"
            data-slide-index="${index}"
            style="--thumb-order:${index}; --thumb-accent:${accentColor}; --thumb-soft:${softColor};"
          >
            <div class="svg-thumb-canvas" aria-hidden="true">
              ${slide.markup}
            </div>
            <div class="svg-thumb-meta">
              <div class="svg-thumb-top">
                <strong>${slide.slide_number}. ${escapeHtml(slide.title)}</strong>
                <span class="svg-thumb-badge">P${slide.slide_number}</span>
              </div>
              <small>${escapeHtml(slide.layout_name)} · ${escapeHtml(slide.slide_type)} · ${escapeHtml(slide.style_preset)}</small>
              ${citationsHtml}
            </div>
          </button>
        `;
      }).join("");

      svgThumbStrip.innerHTML = thumbHtml;
      animateThumbStrip();
    }

    function setSvgDeck(svgDeck, resetIndex = true) {
      if (!svgDeck || !svgDeck.slides || !svgDeck.slides.length) {
        state.svgDeck = null;
        state.svgSlideIndex = 0;
        renderSvgThumbnails();
        updateSvgNav();
        return;
      }
      const isNewDeck = !state.svgDeck || state.svgDeck.deck_id !== svgDeck.deck_id;
      state.svgDeck = svgDeck;
      if (resetIndex || isNewDeck || state.svgSlideIndex >= svgDeck.slides.length) {
        state.svgSlideIndex = 0;
      }
      syncSvgControls(svgDeck);
      renderSvgThumbnails();
      updateSvgNav();
    }

    function updateSvgNav() {
      const total = state.svgDeck && state.svgDeck.slides ? state.svgDeck.slides.length : 0;
      svgPrevBtn.disabled = total <= 1 || state.svgSlideIndex <= 0;
      svgNextBtn.disabled = total <= 1 || state.svgSlideIndex >= total - 1;
      if (!total) {
        svgPageLabel.textContent = "SVG 未生成";
        return;
      }
      const themeLabel = state.svgDeck && state.svgDeck.theme_id ? ` · ${state.svgDeck.theme_id}` : "";
      const fontLabel = state.svgDeck && state.svgDeck.font_preset ? ` · ${state.svgDeck.font_preset}` : "";
      svgPageLabel.textContent = `SVG ${state.svgSlideIndex + 1} / ${total}${themeLabel}${fontLabel}`;
    }

    function renderCurrentSvgSlide() {
      if (!state.svgDeck || !state.svgDeck.slides || !state.svgDeck.slides.length) {
        clearPreviewFrame();
        return;
      }
      const currentSlide = state.svgDeck.slides[state.svgSlideIndex];
      state.previewMode = "svg";
      postViewerMessage({
        type: "viewer-svg",
        title: currentSlide.title,
        meta: `SVG ${state.svgSlideIndex + 1} / ${state.svgDeck.slides.length} · ${currentSlide.slide_type}`,
        markup: currentSlide.markup,
      });
      renderSvgThumbnails();
      updateSvgNav();
    }

    function renderList(items) {
      if (!items || !items.length) {
        return '<div class="slide-card-meta">暂无内容</div>';
      }
      return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    }

    function renderSlideBoard(slidePlan) {
      if (!slidePlan || !slidePlan.slides || !slidePlan.slides.length) {
        slideBoard.innerHTML = '<div class="empty-board">还没有逐页策划。先点击“生成逐页策划”，然后在这里编辑页面卡片。</div>';
        return;
      }
      slideBoard.innerHTML = slidePlan.slides.map((slide) => `
        <article class="slide-card" data-slide-number="${slide.slide_number}">
          <div class="slide-card-header">
            <div>
              <h3>${slide.slide_number}. ${escapeHtml(slide.title)}</h3>
              <div class="slide-card-meta">目标：${escapeHtml(slide.goal)}</div>
            </div>
            <div>
              <span class="pill">${escapeHtml(slide.slide_type)}</span>
              <span class="pill">${escapeHtml(slide.interaction_mode)}</span>
              <span class="pill">${escapeHtml(slide.template_id || "template-pending")}</span>
            </div>
          </div>
          <div class="slide-card-meta">版式建议：${escapeHtml(slide.layout_hint || "卡片式布局")}</div>
          <section>
            <h4>Key Points</h4>
            ${renderList(slide.key_points)}
          </section>
          <section>
            <h4>Visual Brief</h4>
            ${renderList(slide.visual_brief)}
          </section>
          <section>
            <h4>Speaker Notes</h4>
            ${renderList(slide.speaker_notes)}
          </section>
          <div class="card-actions">
            <button class="secondary" data-action="move-up" data-slide="${slide.slide_number}">上移</button>
            <button class="secondary" data-action="move-down" data-slide="${slide.slide_number}">下移</button>
            <button class="secondary" data-action="insert-after" data-slide="${slide.slide_number}">后插页</button>
            <button class="secondary" data-action="edit" data-slide="${slide.slide_number}">编辑</button>
            <button class="secondary" data-action="regenerate" data-slide="${slide.slide_number}">单页再生成</button>
            <button class="secondary" data-action="delete" data-slide="${slide.slide_number}">删除</button>
          </div>
        </article>
      `).join("");
    }

    function renderConfirmation(session) {
      const confirmation = session && session.planning_confirmation;
      if (!confirmation) {
        confirmationBox.textContent = "确认清单将在提交需求后出现。";
        return;
      }
      confirmationBox.innerHTML = `
        <strong>约束确认</strong><br>
        ${escapeHtml(confirmation.summary || "暂无确认结论。")}<br><br>
        ${(confirmation.items || []).map((item) => `
          <div>${item.status === "confirmed" ? "已确认" : "待补充"} · ${escapeHtml(item.label)}：${escapeHtml(item.detail || "未填写")}</div>
        `).join("")}
      `;
    }

    function renderQuality(session) {
      const report = session && session.quality_report;
      if (!report) {
        qualityBox.textContent = "质量报告将在生成策划后出现。";
        return;
      }
      const issues = Array.isArray(report.issues) ? report.issues : [];
      const ruleIssues = issues.filter((issue) => (issue.origin || "rule") !== "ai");
      const aiIssues = issues.filter((issue) => issue.origin === "ai");
      const renderIssueGroup = (title, items, emptyCopy) => `
        <div class="quality-group">
          <strong>${escapeHtml(title)}</strong>
          ${items.length
            ? items.slice(0, 5).map((issue) => `
                <div>${escapeHtml(issue.severity.toUpperCase())} · ${escapeHtml(issue.message)}${issue.slide_number ? `（第 ${escapeHtml(String(issue.slide_number))} 页）` : ""}</div>
              `).join("")
            : `<div>${escapeHtml(emptyCopy)}</div>`}
        </div>
      `;
      qualityBox.innerHTML = `
        <strong>质量检查</strong><br>
        状态：${escapeHtml(report.status || "pending")} · 分数：${escapeHtml(String(report.score ?? "-"))}<br>
        ${escapeHtml(report.summary || "暂无质量摘要。")}<br><br>
        ${renderIssueGroup("规则问题", ruleIssues, "暂无规则问题。")}
        ${renderIssueGroup("AI 审稿问题", aiIssues, "暂无 AI 审稿补充意见。")}
      `;
    }

    function getEvidenceState(session) {
      const retrievalHits = session && Array.isArray(session.retrieval_hits) ? session.retrieval_hits : [];
      const excludedChunkIds = new Set(
        session && Array.isArray(session.excluded_retrieval_chunk_ids)
          ? session.excluded_retrieval_chunk_ids
          : [],
      );
      const selectedHits = retrievalHits.filter((hit) => !excludedChunkIds.has(hit.chunk_id));
      return { retrievalHits, excludedChunkIds, selectedHits };
    }

    function truncateEvidenceCopy(content, maxLength = 180) {
      const compact = String(content || "").replace(/\s+/g, " ").trim();
      if (!compact) {
        return "暂无片段内容。";
      }
      return compact.length > maxLength ? `${compact.slice(0, maxLength)}…` : compact;
    }

    function renderEvidence(session) {
      if (!session) {
        evidenceBox.innerHTML = '<div class="empty-board">提交需求后这里会出现当前命中的资料片段。先勾掉不相关资料，再确认约束。</div>';
        return;
      }
      const { retrievalHits, excludedChunkIds, selectedHits } = getEvidenceState(session);
      if (!retrievalHits.length) {
        evidenceBox.innerHTML = `
          <div class="empty-board">当前还没有证据命中。可以先上传资料，或点击“刷新命中证据”重新检索。</div>
          <div class="evidence-empty-tip">生成前只会使用这里保留下来的命中资料。</div>
        `;
        return;
      }

      evidenceBox.innerHTML = `
        <div class="evidence-summary">命中证据确认：当前保留 ${selectedHits.length} / ${retrievalHits.length} 条资料。取消勾选的命中不会参与后续确认、生成和导出。</div>
        <div class="evidence-list">
          ${retrievalHits.map((hit, index) => {
            const isSelected = !excludedChunkIds.has(hit.chunk_id);
            const title = hit.source_title || hit.source_filename || hit.topic_hint || `命中片段 ${index + 1}`;
            const metaParts = [
              hit.source_type || "knowledge-base",
              hit.page_label || "",
              hit.subject_tag ? `学科：${hit.subject_tag}` : "",
              hit.topic_hint ? `主题：${hit.topic_hint}` : "",
            ].filter(Boolean);
            return `
              <label class="evidence-item ${isSelected ? "" : "is-excluded"}">
                <div class="evidence-item-head">
                  <div>
                    <div class="evidence-item-title">${escapeHtml(title)}</div>
                    <div class="evidence-item-meta">${escapeHtml(metaParts.join(" · ") || "未标注来源")}</div>
                  </div>
                  <span class="evidence-check">
                    <input type="checkbox" data-evidence-chunk-id="${escapeHtml(hit.chunk_id)}" ${isSelected ? "checked" : ""}>
                    <span>保留</span>
                  </span>
                </div>
                <p class="evidence-item-copy">${escapeHtml(truncateEvidenceCopy(hit.content))}</p>
              </label>
            `;
          }).join("")}
        </div>
      `;
    }

    function renderMetric(label, value) {
      return `
        <div class="metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value))}</strong>
        </div>
      `;
    }

    function setStepState(cardNode, topBadgeNode, sideBadgeNode, stepState) {
      const label = STEP_STATE_LABELS[stepState] || STEP_STATE_LABELS.pending;
      if (cardNode) {
        cardNode.dataset.stepState = stepState;
      }
      [topBadgeNode, sideBadgeNode].forEach((node) => {
        if (!node) {
          return;
        }
        node.dataset.stepState = stepState;
        node.textContent = label;
      });
    }

    function renderWorkflow(session) {
      const hasSession = Boolean(session && session.session_id);
      const confirmed = Boolean(session && session.planning_confirmation && session.planning_confirmation.confirmed);
      const hasGeneration = Boolean(
        (session && session.outline && Array.isArray(session.outline.sections) && session.outline.sections.length)
        || (session && session.slide_plan && Array.isArray(session.slide_plan.slides) && session.slide_plan.slides.length)
        || (session && session.svg_deck && Array.isArray(session.svg_deck.slides) && session.svg_deck.slides.length),
      );
      const hasExport = Boolean(session && Array.isArray(session.export_artifacts) && session.export_artifacts.length);

      setStepState(stepIntakeCard, stepIntakeBadge, intakeStateBadge, hasSession ? "done" : "active");
      setStepState(
        stepConfirmCard,
        stepConfirmBadge,
        confirmStateBadge,
        !hasSession ? "pending" : confirmed ? "done" : "active",
      );
      setStepState(
        stepGenerateCard,
        stepGenerateBadge,
        generateStateBadge,
        !hasSession || !confirmed ? "pending" : hasGeneration ? "done" : "active",
      );
      setStepState(
        stepExportCard,
        stepExportBadge,
        exportStateBadge,
        !hasSession || !confirmed || !hasGeneration ? "pending" : hasExport ? "done" : "active",
      );
    }

    function setArtifactChipState(node, label, href) {
      node.textContent = label;
      if (href) {
        node.href = href;
        node.classList.remove("is-disabled");
      } else {
        node.href = "#";
        node.classList.add("is-disabled");
      }
    }

    function renderOverview(session, payload) {
      const spec = session && session.teaching_spec ? session.teaching_spec : null;
      const outline = (session && session.outline) || payload.outline || null;
      const slidePlan = (session && session.slide_plan) || payload.slide_plan || null;
      const svgDeck = payload.svg_deck || (session && session.svg_deck) || null;
      const artifacts = session && Array.isArray(session.export_artifacts) ? session.export_artifacts : [];
      const { retrievalHits, selectedHits } = getEvidenceState(session);
      const uploadedFiles = session && Array.isArray(session.uploaded_files) ? session.uploaded_files : [];
      const quality = session && session.quality_report ? session.quality_report : null;
      const confirmation = session && session.planning_confirmation ? session.planning_confirmation : null;
      const lessonTitle = spec && spec.lesson_title ? spec.lesson_title : (session && session.title ? session.title : "未提交需求");
      const subjectMeta = [
        spec && spec.grade_level ? spec.grade_level : "",
        spec && spec.subject ? spec.subject : "",
        spec && spec.lesson_duration_minutes ? `${spec.lesson_duration_minutes} 分钟` : "",
      ].filter(Boolean);

      overviewBadge.textContent = !session
        ? "等待会话"
        : confirmation && confirmation.confirmed
          ? "已确认，可继续生成"
          : "待确认约束";
      lessonSummaryTitle.textContent = lessonTitle;
      if (subjectMeta.length) {
        const retrievalModeLabel = session && session.web_search_enabled ? "含联网补充检索" : "本地资料优先";
        lessonSummaryMeta.textContent = `${subjectMeta.join(" · ")} · ${retrievalModeLabel}`;
      } else {
        lessonSummaryMeta.textContent = "提交需求后会显示学段、学科、课时和资料边界。";
      }

      progressSummary.innerHTML = [
        renderMetric("资料", uploadedFiles.length),
        renderMetric("证据", selectedHits.length),
        renderMetric("大纲", outline && Array.isArray(outline.sections) ? outline.sections.length : 0),
        renderMetric("页面", slidePlan && Array.isArray(slidePlan.slides) ? slidePlan.slides.length : 0),
        renderMetric("SVG", svgDeck && Array.isArray(svgDeck.slides) ? svgDeck.slides.length : 0),
        renderMetric("质量", quality ? quality.score : "-"),
      ].join("");

      if (!session) {
        retrievalSummary.textContent = "等待会话创建后统计资料、证据命中和生成情况。";
      } else if (!retrievalHits.length) {
        retrievalSummary.textContent = "当前还没有有效证据命中。建议先上传资料，或启用联网补充搜索后重新生成。";
      } else {
        const topSources = [...new Set(retrievalHits.slice(0, 4).map((hit) => hit.source_type || "knowledge-base"))];
        const filteredCount = retrievalHits.length - selectedHits.length;
        retrievalSummary.textContent = filteredCount > 0
          ? `已命中 ${retrievalHits.length} 条参考内容，当前保留 ${selectedHits.length} 条，已剔除 ${filteredCount} 条。主要来源：${topSources.join(" / ")}。`
          : `已命中 ${retrievalHits.length} 条参考内容，主要来源：${topSources.join(" / ")}。`;
      }

      if (artifacts.length) {
        artifactSummary.innerHTML = artifacts.slice(-4).reverse().map((artifact) => {
          const downloadUrl = session
            ? `/api/export/files/${session.session_id}/${artifact.filename}`
            : "#";
          return `
            <li>
              <a href="${escapeHtml(downloadUrl)}" target="_blank" rel="noreferrer">${escapeHtml(artifact.filename)}</a>
              <small> · ${escapeHtml(String(artifact.resource_type).toUpperCase())}${artifact.summary ? ` · ${escapeHtml(artifact.summary)}` : ""}</small>
            </li>
          `;
        }).join("");
      } else {
        artifactSummary.innerHTML = '<li class="summary-empty">暂无导出文件。生成 DOCX 或 PPTX 后会在这里显示。</li>';
      }

      const latestDocx = [...artifacts].reverse().find((artifact) => artifact.resource_type === "docx");
      const latestPptx = [...artifacts].reverse().find((artifact) => artifact.resource_type === "pptx");
      setArtifactChipState(
        artifactDocxChip,
        latestDocx ? `DOCX · ${latestDocx.filename}` : "DOCX 待生成",
        latestDocx && session ? `/api/export/files/${session.session_id}/${latestDocx.filename}` : "",
      );
      setArtifactChipState(
        artifactPptxChip,
        latestPptx ? `PPTX · ${latestPptx.filename}` : "PPTX 待生成",
        latestPptx && session ? `/api/export/files/${session.session_id}/${latestPptx.filename}` : "",
      );

      if (!session) {
        nextActionBox.innerHTML = "<strong>下一步建议：</strong>先提交需求，再查看确认清单并确认约束。";
      } else if (confirmation && !confirmation.confirmed) {
        const missing = Array.isArray(confirmation.missing_items) ? confirmation.missing_items : [];
        nextActionBox.innerHTML = `<strong>下一步建议：</strong>${missing.length ? `先补齐 ${escapeHtml(missing.join("、"))}，` : ""}确认约束后再生成大纲、SVG 和导出。`;
      } else if (!slidePlan || !slidePlan.slides || !slidePlan.slides.length) {
        nextActionBox.innerHTML = "<strong>下一步建议：</strong>约束已确认，下一步先生成课程大纲和逐页策划。";
      } else if (!svgDeck || !svgDeck.slides || !svgDeck.slides.length) {
        nextActionBox.innerHTML = "<strong>下一步建议：</strong>当前已有逐页策划，下一步建议生成 SVG 中间稿并检查版式。";
      } else if (!latestPptx || !latestDocx) {
        nextActionBox.innerHTML = "<strong>下一步建议：</strong>当前已有 SVG 中间稿，下一步建议导出 DOCX 和 PPTX 草稿。";
      } else {
        nextActionBox.innerHTML = `<strong>当前状态：</strong>${escapeHtml(session.last_summary || "本轮流程已跑通，可以继续做页级修改或更换主题后再次导出。")}`;
      }
    }

    function setGenerationAvailability(session) {
      const hasSession = Boolean(session && session.session_id);
      const confirmed = Boolean(session && session.planning_confirmation && session.planning_confirmation.confirmed);
      [outlineBtn, planBtn, previewBtn, svgBtn, exportBtn, exportPptxBtn].forEach((button) => {
        button.disabled = !hasSession || !confirmed;
      });
      addSlideBtn.disabled = !(session && session.slide_plan && session.slide_plan.slides && session.slide_plan.slides.length);
    }

    function updateSession(sessionId, stage) {
      if (sessionId) {
        state.sessionId = sessionId;
      }
      sessionTag.textContent = `Session: ${state.sessionId || "未创建"}`;
      stageTag.textContent = `Stage: ${stage || "intake"}`;
    }

    function renderPayload(payload) {
      state.lastPayload = payload;
      const session = payload.session || payload;
      const sessionSvgDeck = payload.svg_deck || (session && session.svg_deck) || null;
      const sessionSlidePlan = (session && session.slide_plan) || payload.slide_plan || null;
      const previewHtml = payload.preview ? payload.preview.html_document : null;
      syncSvgControls(sessionSvgDeck || session);
      if (session && typeof session.web_search_enabled === "boolean" && webSearchToggle) {
        webSearchToggle.checked = session.web_search_enabled;
      }
      if (session && session.session_id) {
        updateSession(session.session_id, session.stage);
      } else if (payload.session_id) {
        updateSession(payload.session_id, payload.stage);
      }
      workspaceTag.textContent = `Workspace: ${session && session.workspace_path ? session.workspace_path.replace(/\\\\/g, "/").split("/").slice(-2).join("/") : "未创建"}`;
      renderConfirmation(session);
      renderEvidence(session);
      renderQuality(session);
      renderWorkflow(session);
      renderOverview(session, payload);
      setGenerationAvailability(session);
      renderSlideBoard(sessionSlidePlan);
      
      if (previewHtml) {
        state.previewMode = "html";
        postViewerMessage({
          type: "viewer-html",
          title: payload.preview && payload.preview.title ? payload.preview.title : "HTML Preview",
          meta: "当前正在查看低保真预览。",
          html_document: previewHtml,
        });
        setSvgDeck(sessionSvgDeck || state.svgDeck, false);
        updateSvgNav();
      } else if (sessionSvgDeck) {
        setSvgDeck(sessionSvgDeck);
        renderCurrentSvgSlide();
      } else if (!(session && session.preview_deck)) {
        setSvgDeck(null);
        clearPreviewFrame();
      } else {
        setSvgDeck((session && session.svg_deck) || null);
      }
      const artifact = payload.artifact || {};
      if (payload.download_url && artifact.resource_type === "docx") {
        downloadLink.href = payload.download_url;
        downloadLink.hidden = false;
      }
      if (payload.download_url && artifact.resource_type === "pptx") {
        downloadPptxLink.href = payload.download_url;
        downloadPptxLink.hidden = false;
      }
    }

    window.renderPayload = renderPayload;

    async function postJson(url, body) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Request failed");
      }
      return payload;
    }

    async function ensureSvgDeckMatchesSelection() {
      if (!state.sessionId) {
        throw new Error("请先提交需求，生成会话。");
      }
      const selectedTheme = themeSelect.value;
      const selectedFont = fontSelect.value;
      if (
        state.svgDeck &&
        state.svgDeck.theme_id === selectedTheme &&
        state.svgDeck.font_preset === selectedFont
      ) {
        return state.svgDeck;
      }
      const payload = await postJson("/api/svg/deck", {
        session_id: state.sessionId,
        top_k: 5,
        theme_id: selectedTheme,
        font_preset: selectedFont,
      });
      renderPayload(payload);
      return payload.svg_deck;
    }

    async function getSessionPayload() {
      if (!state.sessionId) {
        throw new Error("当前还没有会话。");
      }
      const response = await fetch(`/api/chat/sessions/${state.sessionId}`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Request failed");
      }
      return payload;
    }

    async function refreshSessionView(message) {
      const payload = await getSessionPayload();
      renderPayload(payload);
      if (message) {
        setStatus(message);
      }
    }

    function getExcludedEvidenceChunkIds() {
      if (!evidenceBox) {
        return [];
      }
      return Array.from(evidenceBox.querySelectorAll("input[data-evidence-chunk-id]"))
        .filter((input) => !input.checked)
        .map((input) => input.dataset.evidenceChunkId)
        .filter(Boolean);
    }

    function evidenceSelectionChanged() {
      const session = state.lastPayload ? (state.lastPayload.session || state.lastPayload) : null;
      if (!session) {
        return false;
      }
      const currentExcluded = [...getExcludedEvidenceChunkIds()].sort();
      const savedExcluded = Array.isArray(session.excluded_retrieval_chunk_ids)
        ? [...session.excluded_retrieval_chunk_ids].sort()
        : [];
      return currentExcluded.join("||") !== savedExcluded.join("||");
    }

    async function persistEvidenceSelection(options = {}) {
      if (!state.sessionId) {
        if (!options.silent) {
          setStatus("请先提交需求，生成会话。");
        }
        return null;
      }
      const session = state.lastPayload ? (state.lastPayload.session || state.lastPayload) : null;
      const retrievalHits = session && Array.isArray(session.retrieval_hits) ? session.retrieval_hits : [];
      if (!retrievalHits.length) {
        if (!options.silent) {
          setStatus("当前还没有可选择的命中证据。");
        }
        return session;
      }
      if (!options.force && !evidenceSelectionChanged()) {
        return session;
      }
      const payload = await postJson("/api/evidence/selection", {
        session_id: state.sessionId,
        excluded_chunk_ids: getExcludedEvidenceChunkIds(),
      });
      renderPayload(payload);
      if (!options.silent) {
        setStatus(`证据选择已保存，当前保留 ${payload.selected_count} / ${payload.total_count} 条命中。`);
      }
      return payload.session || payload;
    }

    async function refreshEvidenceHits(options = {}) {
      if (!state.sessionId) {
        if (!options.silent) {
          setStatus("请先提交需求，生成会话。");
        }
        return null;
      }
      const payload = await postJson("/api/evidence/refresh", {
        session_id: state.sessionId,
        top_k: 8,
        use_web_search: webSearchEnabled(),
      });
      renderPayload(payload);
      if (!options.silent) {
        setStatus(`证据命中已刷新，当前保留 ${payload.selected_count} / ${payload.total_count} 条命中。`);
      }
      return payload.session || payload;
    }

    async function syncEvidenceSelectionBeforeGeneration() {
      const session = state.lastPayload ? (state.lastPayload.session || state.lastPayload) : null;
      const retrievalHits = session && Array.isArray(session.retrieval_hits) ? session.retrieval_hits : [];
      if (!retrievalHits.length) {
        return;
      }
      if (evidenceSelectionChanged()) {
        await persistEvidenceSelection({ silent: true });
      }
    }

    async function submitDemand() {
      const title = document.getElementById("title").value.trim() || "Untitled Session";
      const content = document.getElementById("content").value.trim();
      if (!content) {
        setStatus("请先输入教师需求。");
        return;
      }
      setStatus("正在提交需求...");
      try {
        const payload = await postJson("/api/chat/messages", {
          session_id: state.sessionId,
          title,
          content,
          use_web_search: webSearchEnabled(),
        });
        renderPayload(payload);
        setStatus("需求已提交。先看确认清单，确认后再生成大纲和导出。");
      } catch (error) {
        setStatus(`提交失败：${error.message}`);
      }
    }

    window.__submitDemand = async function() {
      const previousSessionId = state.sessionId;
      await submitDemand();
      if (
        statusBox.textContent === "正在提交需求..." &&
        (state.sessionId || previousSessionId)
      ) {
        statusBox.textContent = "需求已提交。";
      }
    };

    sendBtn.addEventListener("click", window.__submitDemand);

    refreshEvidenceBtn.addEventListener("click", async () => {
      try {
        setStatus("正在刷新命中证据...");
        await refreshEvidenceHits({ silent: false });
      } catch (error) {
        setStatus(`刷新失败：${error.message}`);
      }
    });

    applyEvidenceBtn.addEventListener("click", async () => {
      try {
        await persistEvidenceSelection({ force: true });
      } catch (error) {
        setStatus(`保存失败：${error.message}`);
      }
    });

    document.getElementById("refreshConfirmBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求，生成会话。");
        return;
      }
      setStatus("正在刷新确认清单...");
      try {
        await syncEvidenceSelectionBeforeGeneration();
        const payload = await postJson("/api/planner/confirmation/refresh", {
          session_id: state.sessionId,
        });
        renderPayload(payload);
        setStatus("确认清单已刷新。");
      } catch (error) {
        setStatus(`刷新失败：${error.message}`);
      }
    });

    document.getElementById("confirmBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求，生成会话。");
        return;
      }
      const note = window.prompt("可选：记录本次确认说明", "按当前需求和证据边界继续生成");
      setStatus("正在确认约束...");
      try {
        await syncEvidenceSelectionBeforeGeneration();
        const payload = await postJson("/api/planner/confirmation/confirm", {
          session_id: state.sessionId,
          note,
        });
        renderPayload(payload);
        setStatus("约束已确认，现在可以继续生成大纲、SVG 和导出。");
      } catch (error) {
        setStatus(`确认失败：${error.message}`);
      }
    });

    document.getElementById("outlineBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求，生成会话。");
        return;
      }
      setStatus("正在生成课程大纲...");
      try {
        await syncEvidenceSelectionBeforeGeneration();
        const payload = await postJson("/api/planner/outline", {
          session_id: state.sessionId,
          top_k: 5,
          use_web_search: webSearchEnabled(),
        });
        renderPayload(payload);
        setStatus("课程大纲已生成。");
      } catch (error) {
        setStatus(`生成失败：${error.message}`);
      }
    });

    document.getElementById("planBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求，生成会话。");
        return;
      }
      setStatus("正在生成逐页策划...");
      try {
        await syncEvidenceSelectionBeforeGeneration();
        const payload = await postJson("/api/planner/slide-plan", {
          session_id: state.sessionId,
          top_k: 5,
          use_web_search: webSearchEnabled(),
        });
        renderPayload(payload);
        setStatus("逐页策划已生成。");
      } catch (error) {
        setStatus(`生成失败：${error.message}`);
      }
    });

    document.getElementById("previewBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求，生成会话。");
        return;
      }
      setStatus("正在生成低保真预览...");
      try {
        await syncEvidenceSelectionBeforeGeneration();
        const payload = await postJson("/api/preview/deck", {
          session_id: state.sessionId,
          top_k: 5,
        });
        renderPayload(payload);
        setStatus("低保真预览已生成。");
      } catch (error) {
        setStatus(`生成失败：${error.message}`);
      }
    });

    document.getElementById("svgBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求，生成会话。");
        return;
      }
      setStatus("正在生成 SVG 中间稿...");
      try {
        await syncEvidenceSelectionBeforeGeneration();
        const payload = await postJson("/api/svg/deck", {
          session_id: state.sessionId,
          top_k: 5,
          theme_id: themeSelect.value,
          font_preset: fontSelect.value,
        });
        renderPayload(payload);
        const slideCount = payload.svg_deck && payload.svg_deck.slides ? payload.svg_deck.slides.length : 0;
        setStatus(`SVG 中间稿已生成，可翻页预览全部 ${slideCount} 页。`);
      } catch (error) {
        setStatus(`生成失败：${error.message}`);
      }
    });

    document.getElementById("exportBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求，生成会话。");
        return;
      }
      setStatus("正在生成 DOCX...");
      try {
        await syncEvidenceSelectionBeforeGeneration();
        const payload = await postJson("/api/export/docx", {
          session_id: state.sessionId,
          top_k: 5,
        });
        renderPayload(payload);
        setStatus("DOCX 已生成，可以直接点击下载链接。");
      } catch (error) {
        setStatus(`导出失败：${error.message}`);
      }
    });

    document.getElementById("exportPptxBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求，生成会话。");
        return;
      }
      setStatus("正在生成 PPTX...");
      try {
        await syncEvidenceSelectionBeforeGeneration();
        if (
          !state.svgDeck ||
          state.svgDeck.theme_id !== themeSelect.value ||
          state.svgDeck.font_preset !== fontSelect.value
        ) {
          setStatus("正在同步当前 SVG 主题和字体方案...");
          await ensureSvgDeckMatchesSelection();
        }
        const payload = await postJson("/api/export/pptx", {
          session_id: state.sessionId,
          top_k: 5,
          theme_id: themeSelect.value,
          font_preset: fontSelect.value,
        });
        renderPayload(payload);
        setStatus("PPTX 已生成，可以直接点击下载链接。");
      } catch (error) {
        setStatus(`导出失败：${error.message}`);
      }
    });

    document.getElementById("sessionBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("当前还没有会话。");
        return;
      }
      setStatus("正在刷新会话...");
      try {
        await refreshSessionView("会话状态已刷新。");
      } catch (error) {
        setStatus(`刷新失败：${error.message}`);
      }
    });

    document.getElementById("uploadBtn").addEventListener("click", async () => {
      const input = document.getElementById("fileInput");
      if (!input.files.length) {
        setStatus("请先选择一个文件。");
        return;
      }
      setStatus("正在上传文件...");
      const formData = new FormData();
      formData.append("file", input.files[0]);
      if (state.sessionId) {
        formData.append("session_id", state.sessionId);
      } else {
        formData.append("title", document.getElementById("title").value.trim() || "Untitled Session");
      }
      try {
        const response = await fetch("/api/files/upload", {
          method: "POST",
          body: formData,
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail || "Upload failed");
        }
        renderPayload(payload);
        setStatus("文件已上传并完成基础解析。");
      } catch (error) {
        setStatus(`上传失败：${error.message}`);
      }
    });

    document.getElementById("refreshBoardBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("当前还没有会话。");
        return;
      }
      setStatus("正在刷新数字便利贴...");
      try {
        await refreshSessionView("数字便利贴已刷新。");
      } catch (error) {
        setStatus(`刷新失败：${error.message}`);
      }
    });

    document.getElementById("addSlideBtn").addEventListener("click", async () => {
      if (!state.sessionId) {
        setStatus("请先提交需求并生成逐页策划。");
        return;
      }
      const currentSlides = state.lastPayload && state.lastPayload.session && state.lastPayload.session.slide_plan
        ? state.lastPayload.session.slide_plan.slides || []
        : state.lastPayload && state.lastPayload.slide_plan
          ? state.lastPayload.slide_plan.slides || []
          : [];
      const positionInput = window.prompt("插入到第几位？", String(currentSlides.length + 1));
      if (!positionInput) {
        return;
      }
      const title = window.prompt("新页面标题", "补充案例页");
      if (!title) {
        return;
      }
      const goal = window.prompt("新页面目标", "补充与本课主题相关的案例或练习");
      if (!goal) {
        return;
      }
      const keyPointsInput = window.prompt("关键要点，使用中文分号分隔", "案例背景；核心问题；讨论任务");
      const keyPoints = keyPointsInput ? keyPointsInput.split(/[；;\\n]/).map((item) => item.trim()).filter(Boolean) : [];
      setStatus("正在插入新页面...");
      try {
        const payload = await postJson("/api/planner/slide-plan/insert", {
          session_id: state.sessionId,
          position: Number(positionInput),
          title,
          goal,
          key_points: keyPoints,
          revision_note: "front-end insert",
        });
        renderPayload(payload);
        setStatus("新页面已插入。");
      } catch (error) {
        setStatus(`插入失败：${error.message}`);
      }
    });

    slideBoard.addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) {
        return;
      }
      const slideNumber = Number(button.dataset.slide);
      const action = button.dataset.action;
      if (!state.sessionId || !slideNumber) {
        setStatus("当前没有可编辑的页面。");
        return;
      }

      const slides = state.lastPayload && state.lastPayload.session && state.lastPayload.session.slide_plan
        ? state.lastPayload.session.slide_plan.slides || []
        : state.lastPayload && state.lastPayload.slide_plan
          ? state.lastPayload.slide_plan.slides || []
          : [];
      const currentSlide = slides.find((slide) => slide.slide_number === slideNumber);
      if (!currentSlide) {
        setStatus("当前页面数据不存在，请先刷新。");
        return;
      }

      try {
        if (action === "move-up") {
          if (slideNumber === 1) {
            setStatus("当前已经是第一页。");
            return;
          }
          setStatus(`正在上移第 ${slideNumber} 页...`);
          const payload = await postJson("/api/planner/slide-plan/move", {
            session_id: state.sessionId,
            from_slide_number: slideNumber,
            to_position: slideNumber - 1,
          });
          renderPayload(payload);
          setStatus(`第 ${slideNumber} 页已上移。`);
          return;
        }

        if (action === "move-down") {
          if (slideNumber === slides.length) {
            setStatus("当前已经是最后一页。");
            return;
          }
          setStatus(`正在下移第 ${slideNumber} 页...`);
          const payload = await postJson("/api/planner/slide-plan/move", {
            session_id: state.sessionId,
            from_slide_number: slideNumber,
            to_position: slideNumber + 1,
          });
          renderPayload(payload);
          setStatus(`第 ${slideNumber} 页已下移。`);
          return;
        }

        if (action === "delete") {
          if (!window.confirm(`确认删除第 ${slideNumber} 页吗？`)) {
            return;
          }
          setStatus(`正在删除第 ${slideNumber} 页...`);
          const payload = await postJson("/api/planner/slide-plan/delete", {
            session_id: state.sessionId,
            slide_number: slideNumber,
          });
          renderPayload(payload);
          setStatus(`第 ${slideNumber} 页已删除。`);
          return;
        }

        if (action === "edit") {
          const title = window.prompt("页面标题", currentSlide.title);
          if (!title) {
            return;
          }
          const goal = window.prompt("页面目标", currentSlide.goal);
          if (!goal) {
            return;
          }
          const keyPointsRaw = window.prompt(
            "关键要点，使用中文分号分隔",
            (currentSlide.key_points || []).join("；"),
          );
          const keyPoints = keyPointsRaw
            ? keyPointsRaw.split(/[；;\\n]/).map((item) => item.trim()).filter(Boolean)
            : [];
          setStatus(`正在更新第 ${slideNumber} 页...`);
          const payload = await postJson("/api/planner/slide-plan/update", {
            session_id: state.sessionId,
            slide_number: slideNumber,
            title,
            goal,
            key_points: keyPoints,
            revision_note: "front-end edit",
          });
          renderPayload(payload);
          setStatus(`第 ${slideNumber} 页已更新。`);
          return;
        }

        if (action === "insert-after") {
          const title = window.prompt("新页面标题", `${currentSlide.title} · 补充页`);
          if (!title) {
            return;
          }
          const goal = window.prompt("新页面目标", `补充 ${currentSlide.title} 的案例或练习`);
          if (!goal) {
            return;
          }
          setStatus(`正在在第 ${slideNumber} 页后插入新页面...`);
          const payload = await postJson("/api/planner/slide-plan/insert", {
            session_id: state.sessionId,
            position: slideNumber + 1,
            title,
            goal,
            revision_note: "front-end insert-after",
          });
          renderPayload(payload);
          setStatus(`已在第 ${slideNumber} 页后插入新页面。`);
          return;
        }

        if (action === "regenerate") {
          const instructions = window.prompt("补充调整要求", "强化案例、练习或互动环节");
          setStatus(`正在重生成第 ${slideNumber} 页...`);
          const payload = await postJson("/api/planner/slide-plan/regenerate-slide", {
            session_id: state.sessionId,
            slide_number: slideNumber,
            instructions,
          });
          renderPayload(payload);
          setStatus(`第 ${slideNumber} 页已重生成。`);
        }
      } catch (error) {
        setStatus(`操作失败：${error.message}`);
      }
    });

    svgPrevBtn.addEventListener("click", () => {
      if (!state.svgDeck || state.svgSlideIndex <= 0) {
        return;
      }
      state.svgSlideIndex -= 1;
      renderCurrentSvgSlide();
      setStatus(`已切换到 SVG 第 ${state.svgSlideIndex + 1} 页。`);
    });

    svgNextBtn.addEventListener("click", () => {
      const total = state.svgDeck && state.svgDeck.slides ? state.svgDeck.slides.length : 0;
      if (!state.svgDeck || state.svgSlideIndex >= total - 1) {
        return;
      }
      state.svgSlideIndex += 1;
      renderCurrentSvgSlide();
      setStatus(`已切换到 SVG 第 ${state.svgSlideIndex + 1} 页。`);
    });

    svgThumbStrip.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-slide-index]");
      if (!button || !state.svgDeck) {
        return;
      }
      const nextIndex = Number(button.dataset.slideIndex);
      if (Number.isNaN(nextIndex) || nextIndex < 0 || nextIndex >= state.svgDeck.slides.length) {
        return;
      }
      state.svgSlideIndex = nextIndex;
      renderCurrentSvgSlide();
      setStatus(`已切换到 SVG 第 ${state.svgSlideIndex + 1} 页。`);
    });

    themeSelect.addEventListener("change", () => {
      applyUiTheme(themeSelect.value);
      animateThumbStrip();
      if (state.previewMode === "svg") {
        animatePreviewSwap();
      }
    });

    applyUiTheme(themeSelect.value);
    renderWorkflow(null);
    setGenerationAvailability(null);
    clearPreviewFrame();
    document.body.setAttribute("data-front-ready", "1");
    document.body.setAttribute("data-render-payload-ready", typeof window.renderPayload);
