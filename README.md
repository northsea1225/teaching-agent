# Teaching Agent

多模态 AI 互动式教学智能体项目原型。

当前主链路：

`教师输入 -> 会话创建 -> 教学需求结构化 -> 文件解析 / 本地 RAG / 联网搜索 -> 约束确认 -> 课程大纲 -> 逐页策划 -> SVG 中间稿 -> 低保真预览 -> 质量检查 -> DOCX / PPTX 导出`

## 当前进度

已完成：

- 标准 Windows Python 3.12 开发环境
- 项目虚拟环境 `.venv`
- Git 仓库初始化与 `.gitignore` 已就绪，默认忽略密钥、本地环境、知识库索引和导出产物
- FastAPI 基础服务入口
- 根路径最小前端页面
- 会话创建 / 获取 / 消息提交
- 教师需求结构化提取
- 多轮提交时会保留资料边界类约束，避免二次提交后丢失来源范围
- 文件上传与解析
- PDF / DOCX / PPTX / 图片 / 音频基础解析
- 解析结果落盘到 `data/parsed`
- 本地知识库导入脚本
- FAISS 向量索引落盘
- 本地 RAG 检索服务
- 可选联网搜索补充检索
- 对话阶段只抽取明确目标/约束，不再把整段输入直接塞进附加要求
- 生成前命中证据确认，可手动剔除不相关资料
- 约束版大纲与逐页策划生成
- 证据不足时自动收缩页数，并把缺失内容保留为“待补充”
- 正式导出前强制检查约束确认和质量状态，高风险内容会被拦截
- 活动页 / 总结页增加结构门禁，单页再生成只围绕当前页引用和既有要点
- 逐页模板注册表与 `template_id`
- 数字便利贴式页级编辑
- 低保真 HTML 预览生成
- SVG 中间层模型与生成服务
- SVG finalize 后处理
- SVG 主题方案与字体方案切换
- SVG 多页预览与缩略图导航
- DOCX 教案导出
- PPTX 课件导出
- 项目工作区自动落盘
- 约束确认清单与确认接口
- 资料边界确认同时读取文字约束和当前证据状态
- 本地知识库默认视为始终启用的基础来源；上传资料和联网搜索是附加来源
- 质量检查报告
- 基础测试与回归测试
- 前端工作台 / 预览器分离架构
- OpenAI `dialog.py` 结构化抽取底座
- 独立 embedding 网关配置底座
- 候选证据 AI 重排与证据焦点压缩
- `planner.py` 大纲生成独立网关接入
- `planner.py` 逐页策划独立网关接入
- 单页再生成模型版接入
- `quality.py` AI 审稿补充层接入
- `speaker notes / 讲稿` 模型润色层接入
- 阿里云百炼 `text-embedding-v4` 已接入，兼容网关会自动按小批次分段提交 embedding 请求

未完成：

- 更完整的高保真 SVG 设计系统
- 更多跨学科模板和模板细分
- 更细的引用排序和证据打分
- 更强的自动修复型质量检查
- 更完整的 PPTX 高保真视觉还原

## 当前能力

目前系统已经可以：

- 创建一个教学会话
- 输入教师需求并生成 `TeachingSpec`
- 上传参考资料到当前会话
- 将当前会话上传资料直接纳入生成上下文
- 解析 `PDF / DOCX / PPTX / image / audio / txt`
- 将解析结果保存为结构化 JSON
- 导入本地知识库并建立 FAISS 索引
- 使用本地 RAG 检索相关片段
- 统一知识库自动打学科 / 学段 / 主题标签，并按标签过滤检索
- 可选补充联网搜索结果，并在会话内持久化该开关
- 已为 `dialog.py` 准备 OpenAI Responses API + Structured Outputs 接口底座，当前默认关闭
- 已为候选检索命中加入 AI 重排层，失败时自动回退到规则重排
- 已为 `planner.py` 的 LessonOutline 和 SlidePlan 分别准备独立模型网关，不影响 `dialog.py`
- 已为单页再生成接入模型版改写，当前复用 `slide planner` 网关并保留失败回退
- 已为 `quality.py` 接入 AI 审稿补充层，当前复用 `planner` 网关并保留失败回退
- 已为 `speaker notes / 讲稿` 接入模型润色层，当前复用 `slide planner` 网关并保留失败回退
- 已为知识库 embedding 增加独立配置：`EMBEDDINGS_API_KEY / EMBEDDINGS_BASE_URL / EMBEDDINGS_MODEL`
- 前端质量区已按“规则问题 / AI 审稿问题”分组展示
- 生成约束确认清单，并显式确认当前需求边界
- 资料边界会同时显示“你写的来源约束”和“当前上传/检索到的资料范围”
- 多轮提交需求时，资料边界类约束会粘性保留；只有你明确给出新的资料边界时才覆盖旧值
- 即使未上传资料且未开启联网搜索，确认清单也会显示“本地知识库：默认启用”
- 在前端确认当前命中的证据，并手动剔除不相关资料
- 基于检索结果生成 `LessonOutline`
- 基于 `LessonOutline` 生成逐页 `SlidePlan`
- 为每页生成稳定的 `template_id`
- 对 `SlidePlan` 执行删页、插页、改页、调顺序与单页再生成
- 在浏览器中直接编辑 `SlidePlan` 数字便利贴
- 基于 `SlidePlan` 生成 `SvgDeckSpec`
- 对 SVG markup 执行 finalize，补 `title/desc` 元数据并清理空节点
- 在浏览器中逐页翻看 SVG 中间稿
- 将 `SlidePlan` 渲染为 HTML 低保真预览
- 自动生成质量报告，检查确认状态、证据稀缺、缺引用、模板不一致等问题
- 将当前会话导出为 `DOCX` 教案草稿
- 将当前会话基于 `SvgDeckSpec` 导出为 `PPTX` 课件草稿
- 自动为每个会话建立项目工作区，并落盘 `session / spec / outline / slide_plan / svg_deck / report`

示例输入：

```text
初中历史《工业革命》，45分钟，希望加入材料分析和讨论。
高中英语 "Environment Protection"，40分钟，希望加入讨论和项目任务。
初中数学《一次函数》复习课，50分钟，增加练习和小测。
```

## 项目结构

```text
teaching-agent/
  app/
    api/
      chat.py
      evidence.py
      export.py
      files.py
      health.py
      kb.py
      planner.py
      preview.py
      quality.py
      routes.py
      svg.py
    models/
      __init__.py
      schemas.py
      session.py
    services/
      audio.py
      confirmation.py
      dialog.py
      evidence.py
      exporter.py
      openai_dialog.py
      openai_evidence_rerank.py
      openai_planner.py
      openai_quality_review.py
      openai_speaker_notes.py
      openai_slide_regenerator.py
      openai_slide_planner.py
      parser.py
      planner.py
      preview.py
      quality.py
      rag.py
      storage.py
      svg.py
      svg_finalize.py
      template_registry.py
      web_search.py
      workspace.py
    utils/
      logging.py
      paths.py
      prompts.py
    config.py
    main.py
    static/
      css/
        viewer.css
        workbench.css
      js/
        viewer.js
        workbench.js
    templates/
      pages/
        index.html
        viewer.html
  data/
    raw/
    parsed/
    kb/
    workspaces/
  .env.example
  exports/
  scripts/
    check_gateway_raw.py
    check_dialog_provider.py
    check_evidence_rerank_provider.py
    check_embedding_provider.py
    check_planner_provider.py
    check_quality_reviewer_provider.py
    fetch_public_seed.py
    run_pipeline_smoke.py
    check_speaker_notes_provider.py
    check_slide_regenerator_provider.py
    check_slide_planner_provider.py
    ingest_kb.py
    run_dev.py
  tests/
  vector_store/
  README.md
```

## 当前接口

### `GET /`

- 项目概览摘要卡，不直接展示接口原始返回
- 前端架构改为 `workbench + viewer` 双页面

最小前端页面，当前支持：

- 教学需求输入
- 文件上传
- 约束确认清单
- 命中证据确认
- 约束确认按钮
- 大纲生成
- 逐页策划生成
- 数字便利贴编辑
- 四步流程首页：`需求录入 -> 约束确认 -> 生成课件 -> 导出交付`
- SVG 中间稿生成
- SVG 多页预览
- 质量摘要查看
- DOCX / PPTX 导出

### `GET /api/health`

健康检查接口。

### `POST /api/chat/sessions`

创建新会话。

```json
{
  "title": "Cross-subject Session"
}
```

### `GET /api/chat/sessions/{session_id}`

获取指定会话。

### `POST /api/chat/messages`

提交教师需求文本并返回结构化结果。

- `use_web_search` 可选：为当前会话开启联网补充搜索

```json
{
  "title": "Demo",
  "content": "初中历史《工业革命》，45分钟，希望加入材料分析和讨论。",
  "use_web_search": true
}
```

### `POST /api/files/upload`

上传参考资料并挂接到当前会话。

表单字段：

- `file`
- `session_id` 可选
- `title` 可选

当前支持：

- `pdf`
- `docx`
- `pptx`
- `image`
- `audio`
- `txt`

### `POST /api/kb/ingest`

导入本地知识库并构建向量索引。

字段：

- `source_dir` 可选
- `include_parsed_assets`
- `session_id` 可选
- `reset`
- `store_namespace` 可选

### `POST /api/kb/search`

对本地知识库执行相似检索。

```json
{
  "query": "工业革命的影响",
  "top_k": 5
}
```

### `POST /api/planner/confirmation/refresh`

刷新当前会话的约束确认清单和质量状态。

```json
{
  "session_id": "your-session-id"
}
```

### `POST /api/evidence/refresh`

按当前会话条件重新刷新命中证据列表。

```json
{
  "session_id": "your-session-id",
  "top_k": 8,
  "use_web_search": true
}
```

### `POST /api/evidence/selection`

保存当前会话的证据保留/剔除结果。被剔除的 `chunk_id` 不会参与后续确认、生成和导出。

```json
{
  "session_id": "your-session-id",
  "excluded_chunk_ids": ["chunk-a", "chunk-b"]
}
```

### `POST /api/planner/confirmation/confirm`

确认当前约束边界。

```json
{
  "session_id": "your-session-id",
  "note": "按当前需求和证据边界继续生成"
}
```

### `POST /api/planner/outline`

基于当前会话生成课程大纲。

- `use_web_search` 可选：沿用或覆盖当前会话的联网搜索开关

```json
{
  "session_id": "your-session-id",
  "top_k": 5,
  "use_web_search": true
}
```

### `POST /api/planner/slide-plan`

基于当前会话生成逐页策划。

- `use_web_search` 可选：沿用或覆盖当前会话的联网搜索开关

```json
{
  "session_id": "your-session-id",
  "top_k": 5,
  "use_web_search": true
}
```

### `POST /api/planner/slide-plan/update`

更新指定页面内容。

### `POST /api/planner/slide-plan/move`

调整页面顺序。

### `POST /api/planner/slide-plan/insert`

插入新页面。

### `POST /api/planner/slide-plan/delete`

删除指定页面。

### `POST /api/planner/slide-plan/regenerate-slide`

重新生成单页内容。

### `POST /api/svg/deck`

生成 `SvgDeckSpec` 和逐页 SVG markup；支持主题方案和字体方案。

```json
{
  "session_id": "your-session-id",
  "top_k": 5,
  "theme_id": "academy",
  "font_preset": "classroom"
}
```

### `POST /api/preview/deck`

生成低保真 HTML 预览。

```json
{
  "session_id": "your-session-id",
  "top_k": 5
}
```

### `POST /api/quality/report`

刷新并获取当前会话的质量检查报告。

```json
{
  "session_id": "your-session-id"
}
```

### `POST /api/export/docx`

生成 `DOCX` 教案草稿。

```json
{
  "session_id": "your-session-id",
  "top_k": 5
}
```

### `POST /api/export/pptx`

生成 `PPTX` 课件草稿。

```json
{
  "session_id": "your-session-id",
  "top_k": 5,
  "theme_id": "studio",
  "font_preset": "modern"
}
```

### `GET /api/export/files/{session_id}/{filename}`

下载导出文件，当前支持：

- `DOCX`
- `PPTX`

## 运行方式

推荐使用项目虚拟环境：

```bat
C:\Users\15635\teaching-agent\.venv\Scripts\activate
cd C:\Users\15635\teaching-agent
uvicorn app.main:app --reload
```

启动后访问：

- 最小前端页面：`http://127.0.0.1:8000/`
- 首页已改成产品化摘要视图，前端只展示会话摘要、进度与产物
- 独立预览器页面：`http://127.0.0.1:8000/viewer`
- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

## 测试

```bat
C:\Users\15635\teaching-agent\.venv\Scripts\python.exe -m pytest tests -q
```

当前状态：

- 已通过 `93` 个测试
- 仍有 `3` 个第三方依赖 warning（`faiss/swig`），不影响功能
- 已补好 `.env.example` 和 `dialog.py` 的 OpenAI 接入开关，待填入 `OPENAI_API_KEY` 后启用
- 已按第三方 OpenAI 兼容网关配置 `OPENAI_BASE_URL` 与 `gemini-3.1-pro-preview`，`dialog.py` 可真实完成结构化抽取
- `OPENAI_BASE_URL` 应指向兼容 API 根地址，例如 `https://provider.example/v1`，不是控制台页 `/console`
- 已新增 `planner` 专用网关配置：`PLANNER_API_KEY / PLANNER_BASE_URL / PLANNER_MODEL`
- 已新增 `evidence rerank` 专用网关配置：`EVIDENCE_RERANK_API_KEY / EVIDENCE_RERANK_BASE_URL / EVIDENCE_RERANK_MODEL`
- 已新增 `quality review` 专用网关配置：`QUALITY_REVIEW_API_KEY / QUALITY_REVIEW_BASE_URL / QUALITY_REVIEW_MODEL`
- 已新增 `slide planner` 专用网关配置：`SLIDE_PLANNER_API_KEY / SLIDE_PLANNER_BASE_URL / SLIDE_PLANNER_MODEL`
- 已新增 `speaker notes` 专用网关配置：`SPEAKER_NOTES_API_KEY / SPEAKER_NOTES_BASE_URL / SPEAKER_NOTES_MODEL`
- 已新增独立 embedding 配置：`EMBEDDINGS_API_KEY / EMBEDDINGS_BASE_URL / EMBEDDINGS_MODEL / EMBEDDINGS_DIMENSIONS`
- 兼容网关 embedding 已支持自动分批，避免百炼这类 `batch size <= 10` 的限制导致入库失败
- 相同资料重复导入时会按 `chunk_id` 自动跳过，避免知识库索引被重复内容污染
- 第一阶段资料当前保留为官方 `PDF` 类资料，统一存放在 `E:\teaching-agent_resources\public_seed`
- 默认知识库当前只使用 `E:\teaching-agent_resources\public_seed` 与 `E:\teaching-agent_resources\subject_seed` 里的非文本资料，并统一使用 `text-embedding-v4`
- 已从百度网盘历史目录导入 `124` 份教学设计与 `172` 份课件，统一存放在 `E:\teaching-agent_resources\subject_seed\history`
- 导入时已删除 `10` 个视频文件；历史学科当前有效资料为 `292` 份，其中 `119` 份 `docx`、`173` 份 `pptx`
- 已从 `D:\BaiduNetdiskDownload` 英语资料中整理出 `438` 个源文件，迁移 `222` 份教学设计和 `215` 份课件到 `E:\teaching-agent_resources\subject_seed\english`
- 当前英语学科已确认入库 `108` 份 `docx` 与 `64` 份 `pptx`；老式 `.doc/.ppt` 原件保留但暂未入库
- 当前默认知识库总量为 `20853` 个 chunk
- 当前 `dialog.py / LessonOutline / SlidePlan` 三处都统一走第一个中转站，仍保留独立配置键位
- 当前 `speaker notes / 讲稿` 模型润色默认复用 `slide planner` 网关，也就是当前第一个中转站
- 当前候选证据 AI 重排默认复用 `planner` 网关；如未单独配置，会自动继承第一个中转站
- 当前 AI 审稿补充层默认复用 `planner` 网关，但默认只有在“约束已确认”后才会触发
- 当前单页再生成默认复用 `slide planner` 网关，也就是当前第一个中转站

## 远程桥接上下文

- 已新增远程桥接上下文文件：
  - `C:\Users\15635\teaching-agent\docs\remote_context.md`
- 已新增远程工作日志模板：
  - `C:\Users\15635\teaching-agent\docs\remote_log.md`
- 飞书桥接到的 Codex 会话不会自动共享当前网页/API 会话历史
- 如需在飞书里延续当前项目背景，优先让它读取 `remote_context.md`
- 如需让本地会话回来后快速接上，建议每次远程结束前更新 `remote_log.md`
- 首页“提交需求”已补回成功状态提示，静态控制按钮统一为 `type="button"`
- 首页“提交需求”增加独立的内联提交流程，不再依赖主脚本全部初始化完成
- 首页主脚本中的残留语法片段已清理，前端可正常进入就绪状态并响应提交
- 首页“提交需求”已改成前置独立入口，即使后续主脚本局部初始化失败，也能先完成需求提交
- 修复首页主脚本在 `workspace_path.replace(...)` 处的转义错误；此前浏览器会在这里整段脚本解析失败，导致提交后其余按钮全部无响应
- 首页 Step 2 已加入“命中证据确认”，可在前端手动勾掉不相关资料，并在生成前自动同步到会话
- 首页前端已从 `app/main.py` 内联大字符串拆成 `app/templates/pages/index.html + app/static/css/workbench.css + app/static/js/workbench.js`
- 新增独立预览器页面 `app/templates/pages/viewer.html`，由工作台通过 `postMessage` 推送 HTML/SVG 预览内容
- 为 `dialog.py` 新增 OpenAI 结构化抽取底座，默认通过 `USE_OPENAI_DIALOG=false` 保持关闭
- 为 `planner.py` 新增独立模型网关，当前 `LessonOutline` 已接入并保留失败回退到规则版
- 为 `planner.py` 新增 `SlidePlan` 独立模型网关，当前与 `LessonOutline` 共享第一个中转站配置，保留失败回退到规则版

## 当前 RAG / 工作区实现

当前版本包括：

- 文本分块
- 默认本地 hash embedding
- `FAISS IndexFlatIP` 检索
- 统一索引下的 `subject/stage/topic` 自动标签推断
- 按学科 / 学段 / 课题关键词过滤知识库命中
- 从 `data/kb` 导入资料
- 可选导入 `data/parsed` 下的解析结果
- 可选使用 `DuckDuckGo Lite` 联网补充搜索，默认关闭
- 当前会话上传资料与知识库命中合并使用
- 当前会话支持手动排除不相关命中，并只用保留证据参与确认、生成与导出
- 自动在 `data/workspaces/<session_id>/` 下写入工作区快照

工作区当前会落盘：

- `session.json`
- `manifests/project_manifest.json`
- `snapshots/teaching_spec.json`
- `snapshots/lesson_outline.json`
- `snapshots/slide_plan.json`
- `snapshots/svg_deck.json`
- `reports/planning_confirmation.json`
- `reports/quality_report.json`

## 下一步计划

当前优先级：

1. 继续补充 SVG 高保真页面模板
2. 继续降低幻觉，优化需求约束、检索排序与证据复用
3. 扩充主题库与字体库
4. 优化上传资料与知识库引用排序
5. 补充更多跨学科模板
6. 继续补齐更多 SVG 组件到 `PPTX` 的细节映射
7. 提升质量报告的规则颗粒度与自动修复能力

## 进度日志

### 2026-03-21

- 建立 FastAPI 最小可运行入口
- 完成 PDF / DOCX / PPTX / 图片 / 音频基础解析
- 完成本地 RAG 与 FAISS 索引
- 完成 `D:\files` 的知识库重建导入
- 完成大纲生成、逐页策划、预览、SVG、DOCX、PPTX 主链路
- 完成 SVG 模板、主题、字体、缩略图导航和引用标签同步
- 完成可选联网搜索服务接入
- 完成约束版大纲与逐页策划生成
- 完成项目工作区自动落盘
- 完成约束确认清单、确认接口和前端联动
- 完成逐页模板注册表和 `template_id`
- 完成 SVG finalize 后处理
- 新增无 AI 条件下的检索硬过滤，拦截模板占位词和明显异学科命中
- 逐页策划改为按页面择优取证，不再把全局命中平均喷到所有页面
- 质量门禁新增学习目标过泛、模板残留、异学科污染拦截
- `scripts/ingest_kb.py` 新增 `--include-keyword / --exclude-keyword`，便于重建单学科知识库
- 知识库改为统一索引自动标签：为原始资料推断 `subject / stage / topic`
- 检索接口和生成链路支持按 `subject / stage / topic_keywords` 过滤命中
- 已用新的自动标签逻辑重建 `D:\files` 到默认知识库
- 修复首页“提交需求”成功后状态未回写的问题，避免界面停留在“正在提交需求...”
- 首页改成四步流程：`需求录入 -> 约束确认 -> 生成课件 -> 导出交付`
- 完成质量检查报告接口和前端摘要展示
- 收紧生成质量：资料不足时压缩页数，缺引用内容标记为高风险
- 收紧需求抽取和检索排序：只保留明确约束片段，并优先命中课题锚点更强的资料
- 收紧正式导出门禁：未确认约束或质量状态为 `blocked/review` 时拒绝导出
- 收紧结构层：活动页必须有任务结构，总结页必须回扣目标，单页再生成不再跨页扩写
- 首页 Step 2 新增“命中证据确认”，允许手动剔除不相关资料并在生成前自动同步
- 前端结构清理：首页已拆成独立的 HTML / CSS / JS 文件，避免继续在 `app/main.py` 里堆叠页面逻辑
- 前端架构继续对齐 `ppt-master` 风格：工作台页和预览器页分离，预览 iframe 不再直接写 `srcdoc`
- 补齐 `dialog.py` 的 OpenAI 接入准备：配置项、`.env.example`、Structured Outputs prompt 与服务模块
- 新增 `scripts/check_dialog_provider.py`，用于快速验证第三方 OpenAI 兼容模型是否能返回结构化教学需求
- 新增 `scripts/check_gateway_raw.py`，用于直接查看中转站 `/chat/completions` 的原始状态码和响应体
- 新增 `planner.py` 的独立网关接入：当前通过单独配置把 `LessonOutline` 路由到指定中转站
- 新增 `scripts/check_planner_provider.py`，用于快速验证当前 `planner` 网关能否生成 `LessonOutline`
- 新增 `scripts/check_evidence_rerank_provider.py`，用于快速验证当前候选证据 AI 重排网关
- 新增候选证据 AI 重排层：先规则清洗，再用模型对干净候选做二次排序，并把证据焦点回写到 `topic_hint`
- 新增 `scripts/check_slide_planner_provider.py`，用于快速验证当前 `SlidePlan` 网关能否返回逐页策划草案
- 新增 `scripts/check_quality_reviewer_provider.py`，用于快速验证当前 AI 审稿补充层
- 新增 `scripts/check_speaker_notes_provider.py`，用于快速验证当前 `speaker notes / 讲稿` 润色网关
- 新增 `scripts/check_embedding_provider.py`，用于快速验证当前 embedding 网关
- 新增 `scripts/fetch_public_seed.py`，用于从公开渠道抓取课程标准、指南和教学标准资料；若 `E:\teaching-agent_resources\public_seed` 存在，则默认写入该目录
- 新增 `scripts/recycle_legacy_ppt.ps1`，用于把原始资料目录里的老式 `.ppt` 送进 Windows 回收站
- 新增 `scripts/probe_url.py`，用于临时探查公开网页的正文和链接结构，方便批量补充学科资料
- 新增 `scripts/fetch_history_seed.py`，用于批量抓取历史学科公开专题资料并落到 `E:\teaching-agent_resources\subject_seed\history`
- 新增 `scripts/fetch_math_seed.py`，用于批量抓取数学学科公开知识点资料并落到 `E:\teaching-agent_resources\subject_seed\math`
- 新增 `scripts/fetch_english_seed.py`，用于批量抓取英语学科公开学习资料并落到 `E:\teaching-agent_resources\subject_seed\english`
- 新增 `scripts/delete_fetched_text_resources.ps1`，用于清理我抓取的 `.txt/.json` 文本型资料，保留 `pdf/pptx/docx/zip`
- 新增 `scripts/organize_original_seed.py`，用于把 `E:\teaching-agent_resources\original_seed` 中的原始资料按第一阶段/第二阶段与学科类别搬运到对应目录
- 新增 `scripts/import_history_baidu_seed.py`，用于把百度网盘下载的历史课件/教案去视频、去重后迁移到 `E:\teaching-agent_resources\subject_seed\history`
- 新增 `scripts/import_english_baidu_seed.py`，用于把百度网盘下载的英语课件/教案去重后迁移到 `E:\teaching-agent_resources\subject_seed\english`
- 新增 `scripts/inspect_baidu_history_dirs.py`，用于统计百度网盘历史资料目录中的文件数量、体积与扩展名分布
- 新增 `scripts/ingest_supported_seed.py`，用于按支持格式和批次把 `pdf/docx/pptx` 资料稳定导入知识库
- 新增 `scripts/summarize_kb_sources.py`，用于按来源路径汇总当前向量库里已经入库的 chunk 与文件数量
- 公开资料抓取脚本已兼容部分站点证书链异常，并在单个来源失败时继续抓取其余来源
- 公开资料抓取脚本会自动跳过伪装成附件的 HTML 壳页，避免把 `viewer.html` 这类无效页面当资料入库
- 第一阶段公开补库优先覆盖：学前、义务教育、高中、职教、高教与国家智慧教育平台官方页面
- 第一阶段公开资料已扩到 `100+` 份原始文件，包含课程标准 PDF、官方解读、平台建设与学前/职教/高教政策材料
- 默认知识库已按当前保留的 `public_seed + subject_seed` 非文本资料重建，重建后基线为 `6924` 个 chunk
- 新导入的百度网盘历史资料共 `306` 个文件，其中迁移进历史资料目录 `296` 个、删除视频 `10` 个、重复文件 `0` 个
- 当前历史学科已成功入库 `292` 份受支持资料，贡献 `7549` 个 chunk；其中 `E:\teaching-agent_resources\subject_seed\history\教学设计` 为 `119` 份 `docx`，`E:\teaching-agent_resources\subject_seed\history\课件` 为 `167` 份 `pptx`
- 另有 `5` 份老式 `.doc` 已保留原件但暂未入库
- 当前默认知识库总量已提升到 `14102` 个 chunk
- 已从 `D:\BaiduNetdiskDownload` 英语资料中整理出 `438` 个源文件，迁移 `222` 份教学设计和 `215` 份课件到 `E:\teaching-agent_resources\subject_seed\english`，删除重复文件 `1` 个，未发现视频文件
- 当前英语学科已确认入库 `108` 份 `docx` 教学设计与 `64` 份 `pptx` 课件；老式 `.doc/.ppt` 原件保留但暂未入库
- 当前默认知识库总量已提升到 `20853` 个 chunk
- 新增 `scripts/run_pipeline_smoke.py`，用于串联回归“需求 -> 证据 -> 确认 -> 大纲 -> 逐页策划 -> 质量报告”
- 新增 `scripts/check_slide_regenerator_provider.py`，用于快速验证当前单页再生成网关
- 保留 `LessonOutline` 与 `SlidePlan` 的双配置结构，但当前运行时统一指向第一个中转站
- `SlidePlan` 和单页再生成都会在结构生成后追加一层模型化 `speaker notes` 润色，只改口播表达，不改结构和事实
- 单页再生成优先走模型改写，失败时自动回退到原来的规则版重组
- 质量报告在硬规则门禁之外新增 AI 审稿补充层，但默认只在约束确认后触发
- 补充测试并跑通当前全部用例
- 修复兼容网关 embedding 重建时的两处问题：自动分批提交向量请求，并在 `--reset` 场景下忽略旧索引维度重新建库
好长的README
