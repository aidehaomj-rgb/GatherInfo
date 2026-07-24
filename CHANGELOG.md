# Changelog

## [0.5.2] - 2026-07-24

### Added
- Added project-level Codex hook configuration to verify the required gstack setup before AI-assisted skill usage.
- Added portable local start/stop helper scripts for the FastAPI backend and Vite frontend.

### Changed
- Bumped project version from `0.5.1` to `0.5.2`.
- Unified version metadata across root package metadata, frontend package metadata, frontend lockfile, backend API metadata, health output, and `VERSION`.
- Updated development service cleanup so local dashboard stop actions clear stale PID files and release ports 8109/5178 reliably.
- Updated `.env.example` to point frontend requests at the current `/api/v1` backend base URL.

### Notes
- `.workbuddy/` is treated as local-only workspace notes and is excluded from Git.

## [0.5.1] - 2026-07-04

### Added
- Added release notes for the current RiskInfoRader project state.
- Added project assets and UI components used by the refreshed intelligence cockpit.

### Changed
- Bumped project version from `0.5.0` to `0.5.1`.
- Synced frontend package metadata and backend API/health version metadata.
- Updated repository ignore rules to keep local runtime data and dependency folders out of Git.

### Notes
- This release captures the local TradeRadar/RiskInfoRader worktree for publication to GitHub.

## [0.5.0] — 2026-06-30

### 新增功能
- **外部信息源批量导入**：从 Excel 总表导入 250 个外部信息源，按两级分层分组入库（平台级 L1 / 类别级 L2，存入 `default_categories`），覆盖网页执法/热点信息、微信公众号、微博、今日头条
- **信息源分层分组展示**：SourcesPage 新增「分层分组 / 平铺列表」视图切换，L1/L2 分组均可折叠展开，便于管理和查找
- **YMG-Deep 深度分析集成**：智能报告页新增 YMG-Deep 面板，用户选择信息集后系统生成分析主题（≤200字）并连同信息摘要转发到本地 YMG-Deep 项目启动深度分析；新增后端端点 `GET /api/v1/ymg-deep/health`、`POST /api/v1/ymg-deep/analyze`
- **智能报告模式分离**：明确区分「单一主题生成报告」与「多主题批量处理」两类，单一主题支持批次复选 + 合并为一份/按批次分别生成两种方式

### 改进
- **模型配置区分可用/未配置**：ModelConfigPage 分「可用模型 / 未配置模型」两个 tab，带统计与状态标记；报告功能仅展示可用模型供选择
- **通知管理分类聚合**：NotificationsPage 按 channel×is_active 分组聚合展示，顶部统计概览，每组可折叠
- **输出目录选择器**：SettingsPage 输出目录改为只读 + 「选择目录」按钮，弹窗含预设目录与自定义路径输入

## [0.4.3] — 2026-06-17

### 新增功能
- **主题采集增强**：`TopicsPage` 支持采集过程实时状态反馈、采集窗口提示与更友好的触发体验
- **译文展示完善**：非中文信息条目翻译结果展示更完整，翻译服务错误处理更健壮
- **条目列表增强**：新增来源详情字段展示，条目筛选与查询接口返回更丰富的元数据
- **信息源路由补齐**：`sources.py` 新增缺失接口点，保持与前端信息源管理页一致

### 维护
- 生成多份贸易政策/出口管制/技术性贸易措施情报报告（DOCX/PDF）
- 新增文档：`docs/api-budget-request-2026.md`、`docs/source-audit-2026-06-13.md`

## [0.4.2] — 2026-06-09

### Bug 修复
- **仪表盘页面加载失败**：修复 DashboardPage.tsx 中两个 `useMemo` hooks（`sourceBarOption`、`maxTagCount`）位于早期 return 之后导致的 React "Rendered more hooks" 错误，将 hooks 上移至 early return 前，引用改为 `data?.` 可选链

### 维护
- `.gitignore` 新增 `data/backups/` 规则，排除数据库备份目录

## [0.4.0] — 2026-06-07
## [0.4.1] — 2026-06-07

### 新增功能
- **采集类别下拉选择**：TopicsPage 新建/编辑主题时，下拉选择所有已设定的采集类别（之前仅显示「无类别」）
- **Ollama 模型扩展选择**：ReportsPage 模型下拉自动发现 Ollama 本地所有模型，支持按具体模型名生成报告
- **报告引擎模型选择修复**：背景任务不再强制使用默认模型，改为使用用户选定的模型；新增 model_name_override 参数


### 新增功能
- **批量生成子模式**：选中'仅使用指定批次'时，可选择'按批次分别生成'（每个选中批次各生成一份报告）或'合并为一份报告'（同主题所有选中批次合并生成一份报告）
- **多批次合并报告**：后端支持 `collection_run_ids` 列表参数，使用 `SQLAlchemy .in_()` 过滤多个采集运行
- **后端背景任务修复**：报告生成背景任务使用 `SimpleNamespace` 重构，避免 `model_attrs` 捕获后跨 session 过期

### Bug 修复
- **主题类别为空**：TopicsPage load 函数未加载 categories，新增 fetchCategories() API 调用
- **报告模型忽视选择**：report_engine.py 背景任务 _complete_report 始终查询 is_default 模型，改为使用已捕获的 model_attrs
- **模型名称可覆写**：新建 ReportGenerateRequest/BatchGenerateRequest 的 model_name_override 字段，支持 Ollama 等 provider 的任意本地模型


### 新增功能
- **采集历史独立页面**：`HistoryPage` 组件，活跃任务实时追踪 + 已完成批次展开查看
- **批量删除条目**：ItemsPage 复选 + 全选（跨页调用 `GET /items/ids`），工具栏删除
- **信息批次标签**：`batch_label`（主题名\_时间戳），ItemsPage 批次筛选下拉
- **关键词模板推荐**：`recommendTemplates()` 根据输入关键词自动匹配 ★推荐模板
- **信息源多选下拉**：MultiSelect 组件替代 checkbox 网格，节省显示空间
- **搜索连接器分发器**：`SearchEngineDispatcher` 支持 Baidu / Bing / 360 搜索
- **采集历史 API**：`GET /runs/batches`（批次分组）、`GET /runs/active`（活跃任务）
- **条目 ID 查询 API**：`GET /items/ids` 返回匹配筛选条件的所有条目 ID
- **模型设为默认**：卡片底部一键「设为默认」按钮，默认模型排最前

### Bug 修复
- **Bad Gateway 502**：`scripts/dev.sh` 后端端口 8108 与 Vite proxy 目标 8109 不匹配 → 统一为 8109
- **采集窗口不生效**：`engine.py` 传递 `window_start` 参数，Tavily 解析 `published_date` 字段
- **关键词不相关条目入库**：`_persist_items()` 新增关键字匹配过滤，不匹配则跳过
- **自动报告未触发**：手动采集后 fire-and-forget 触发 auto_report
- **报告引用无链接**：报告提示词包含原文 URL，RenderMarkdown 支持 markdown 链接语法

### 重构
- `settings.py` 采集历史移出 → 独立 `HistoryPage.tsx`
- `App.tsx` 导航新增「采集历史」菜单
- SettingsPage 导入/导出从大卡片缩为紧凑按钮行
- 报告设置输入框文字加深（`--ink-muted` 调整）

### 数据库迁移
- `collection_runs` 新增列：`batch_id VARCHAR(80)`
- `topics` 新增列：`schedule_cron VARCHAR(100)`, `next_run_at TIMESTAMP`

### 配置变更
- `scripts/dev.sh`：后端端口 8108 → 8109
- `Dev Dashboard`：GatherInfo 项目新增 `stop_cmd` 强制清理 8109+5178 端口
- `.gitignore`：新增 `data/gather.db*`、`logs/`、`.dev-pids`、`AGENTS.md`、`save_memory.md`、`VERSION`、`CHANGELOG.md`

## [0.3.0] — Previous release
- API versioning, OpenAPI docs, error boundary, rate limiting
