# Remote Context

这份文件用于给飞书桥接到的 Codex 会话快速补上下文。

## 项目定位

- 项目名：`teaching-agent`
- 目标：做一个多模态 AI 教学智能体，支持教师输入需求、检索资料、生成课程大纲、逐页策划、SVG 中间稿、DOCX/PPTX 导出。
- 当前阶段：`可运行原型 + 主链路已跑通 + 多处已接入模型`

## 当前主链路

`教师输入 -> 需求结构化 -> 证据检索/筛选 -> 约束确认 -> LessonOutline -> SlidePlan -> SVG/预览 -> 质量检查 -> DOCX/PPTX`

## 当前 AI 接入状态

以下环节已经接入模型：

- `dialog.py`
  - 教学需求结构化
- `planner.py`
  - `LessonOutline` 生成
  - `SlidePlan` 生成
  - 单页再生成
  - `speaker notes` 润色
- 检索后证据 AI 重排
- `quality.py`
  - AI 审稿补充层

说明：

- 这些环节统一走当前第一个中转站
- 失败时保留规则回退，不会直接崩

## 当前知识库状态

当前默认知识库已经重建，只保留：

- `E:\teaching-agent_resources\public_seed`
- `E:\teaching-agent_resources\subject_seed`

不再包含之前删除掉的网页文本型资料向量。

当前状态：

- embedding：`text-embedding-v4`
- 总 chunk 数：`6924`

## 当前资料目录

- 第一阶段资料：
  - `E:\teaching-agent_resources\public_seed`
- 第二阶段资料：
  - `E:\teaching-agent_resources\subject_seed`

当前第二阶段原始分类结果：

- `history`: `6`
- `chemistry`: `23`
- `computer`: `11`
- `electrical`: `7`
- `physics`: `4`
- `accounting`: `1`

说明：

- `E:\teaching-agent_resources\original_seed` 已清空
- 老式 `.ppt` 已送进回收站

## 飞书桥接说明

- 当前已接通 `claude-to-im` 到飞书
- 飞书桥接会话与当前网页/API 聊天是两套独立上下文
- 如果需要在飞书里接续当前项目背景，优先读取本文件

## 当前最重要的工程事实

- 不要再把网页文本型资料当第二阶段主资料
- 第二阶段应优先补：
  - `pptx`
  - `pdf`
  - `docx`
- 当前知识库检索质量的关键，不是继续堆网页文本，而是继续补真实课件/教材类资料

## 常用路径

- 项目根目录：
  - `C:\Users\15635\teaching-agent`
- README：
  - `C:\Users\15635\teaching-agent\README.md`
- 当前上下文文件：
  - `C:\Users\15635\teaching-agent\docs\remote_context.md`
- 向量库：
  - `C:\Users\15635\teaching-agent\vector_store`

## 建议飞书会话首先执行的事

1. 读取本文件
2. 读取 `README.md`
3. 确认当前服务是否在运行
4. 再根据最新任务继续工作
