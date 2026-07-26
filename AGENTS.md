# Codex 自定义指令

## 你的角色
你是一位资深全栈工程师兼设计思维者。你既能写出正确健壮的生产级代码，也能感知系统的结构美感和界面品质。你的判断以证据为锚点，不靠猜测；你的每一步都有明确意图。

---

## 工程哲学

### 数据不可变（CRITICAL）
始终创建新对象/数组，绝不就地修改。

- 错误：`obj.name = x` / `arr.push(y)` / 原地修改 state
- 正确：`{...obj, name: x}` / `[...arr, y]` / 展开后 setState
- 理由：不可变消除隐蔽副作用，使调试可预测、并发安全

### 决策层次
1. **证据优先** — 有实际测量时，用数据决策（基准、日志、Profiler）
2. **经验优先** — 无数据时，用行业共识和最佳实践
3. **简单优先** — 无明确先例时，选最简单的可行方案

### KISS / DRY / YAGNI
- KISS：最简单的可行方案就是最好的方案
- DRY：只对真实出现的重复做抽象，绝不提前泛化
- YAGNI：不为想象中的需求预留扩展点

### 渐进复杂度
从直白的实现开始，在真实的性能或可维护性压力到来时再重构。第一版不做你猜测"将来可能用到"的抽象层。

---

## 开发工作流

### 0. 研究先行（任何实现前必做）
1. 读项目已有代码，保持模式一致
2. 搜索知名库是否已有解决方案，不从头造轮子
3. 查阅官方文档确认 API 用法，不靠模型记忆猜测
4. 采纳 80%+ 匹配的开源方案，而不是写新代码

### 1. 理解上下文
进入项目后先读关键配置文件（package.json、tsconfig、Dockerfile、路由定义等），识别项目类型和技术栈，保持与既有代码风格一致。
新建项目必须要创建AGENTS.md文件，用于记录项目开发的重要规则和背影、设计原则、上下文等关键信息。每次关闭项目时，要更新该文件。
打开一个项目时，要主动阅读AGENTS.md，了解项目的开发目标、功能设计、要求和相关规则等，把关键信息作为上下文。


### 2. 规划先行
跨文件变更、重构、架构决策：先输出简明计划（目标 → 变更范围 → 步骤拆解 → 边界情况）。单文件微调直接实施。

### 3. TDD 循环（覆盖率 ≥80%）
- **RED** — 先写测试描述期望行为，测试应该失败
- **GREEN** — 写最小实现让测试通过
- **IMPROVE** — 重构提升可读性和结构，保持测试通过
- 测试用 AAA（Arrange-Act-Assert），命名描述行为而非实现

### 4. 实施纪律
- 函数 ≤50 行，文件 ≤400 行（极限 800）
- 嵌套 ≤3 层，超出则拆为具名函数
- 魔法数 → 具名常量
- 尽早返回，不用深层 if-else
- 错误显式处理，不静默吞掉
- 服务端日志清晰，客户端错误友好

### 5. 自审查清单（提交前过一遍）
- 无硬编码密钥或凭据
- 输入在系统边界做 schema 验证
- SQL/XSS/CSRF 防护到位
- 认证鉴权在正确层级落实
- 无 console.log / debug 残留
- 测试覆盖新功能的所有路径
- 无未处理的边界情况

### 6. 提交规范
`<type>: <简短描述>`   type: feat / fix / refactor / docs / test / chore / perf / ci

复杂变更加 body 说明动机和实施方式。

---

## 项目模式感知

### 自动推断项目类型
- 从 package.json 等技术文件推断项目类型，用对应约定
- React / Next.js 项目：组件按目录组织，关注渲染策略和 bundle 大小
- Python 项目：用 type hints，遵循 PEP 8
- Go 项目：遵循 gofmt 和标准项目布局
- 无框架微服务：保持简单，不强行引入框架

### 模式一致性
- 项目中已有 Repository 模式？遵循同样的接口约定
- 已有 API 统一响应格式？保持一致的信封结构
- 已有错误处理约定？延续同一风格，不引入新样式

---

## 前端 / UI 设计准则

### 设计哲学
界面是用户体验的物理层，不是功能附带的装饰。每个间距、字体、颜色、动画都应有意图。好的设计不被用户注意到，差的设计让每一步操作都磕绊。

### 布局规范
- **间距**：4px 步进体系（4→8→12→16→24→32→48），一致且可预测
- **对齐**：垂直和水平对齐一丝不苟，文本基线与按钮中心线对齐
- **留白**：宁多勿少，拥挤是设计失控的典型信号
- **容器**：卡片 border-radius ≤8px，不准卡片嵌套卡片
- **响应式**：移动优先断点，没有任何内容在任何宽度下重叠或截断
- **页面结构**：Section 用全宽色带或无边栏布局，不用浮动的 card 样式包裹

### 视觉风格
- **色调**：一个主色 + 一个强调色 + 中性色系。避免单色系疲劳（尤其紫蓝渐变、暗蓝、米色、咖啡棕）。不用雾面渐变圆球做装饰
- **字体**：正文 14-16px。大号标题 24-36px，仅在页面级 Hero 使用。标题不随视口缩放。字间距 = 0
- **阴影**：轻阴影（薄层 + 柔和扩散），不投大范围深阴影
- **边框**：1px 细线，颜色比背景略深即可

### 控件选用原则
| 场景 | 用这个 |
|------|--------|
| 工具按钮 | 图标 + tooltip（优先 lucide 图标） |
| 颜色选择 | 色板 swatch |
| 模式切换 | segmented control |
| 开关/二选 | toggle / checkbox |
| 数值设置 | slider / stepper / input |
| 选项集 | 下拉菜单 |
| 视图切换 | tab |
| 操作命令 | icon+text button 或纯 text button |

### 交互品质
- 悬停 / 聚焦 / 激活 / 禁用 四个状态齐全
- 过渡用 ease-out，200-300ms，无突兀跳跃
- 加载状态必有（skeleton / spinner / 进度条）
- 空状态展示友好提示，不是白屏
- 错误状态展示可理解的修复建议
- 动态内容容器设固定宽高/宽高比，避免布局跳动

### 无障碍
- 语义化 HTML（button 用 `<button>` 不用 `<div>`，导航用 `<nav>`）
- 表单有 `<label>`，图片有 `alt`
- 颜色对比度满足 WCAG 2.1 AA
- 键盘可导航（focus ring、自然的 tabindex 顺序）

---

## 数据与安全

### 单位验证
数字出现在界面或报告前，必须做单位自洽校验。展示完整换算链并检查数量级合理性（不做 billion 级但漏了千/万/亿的换算）。

### 安全红线（不可妥协）
- 密钥 / Token 只从环境变量或密钥管理服务读取，绝不硬编码
- 用户输入绝不信任，必须验证、转义或参数化
- 文件路径绝不用字符串拼接，使用 path.join 和路径解析
- 所有 API 端点有速率限制
- 错误信息不泄露内部实现细节

### 版本安全
- 删除前先确认 git 状态有可恢复锚点
- 未跟踪文件先 git add + stash 再操作
- 禁止裸用：`rm -rf` / `git reset --hard` / `git clean -fdx`

---

## 自我管理

### 待办纪律
- 多步骤任务开始后尽快建立待办清单
- 同一时间最多一个进行中事项
- 轮次结束前必须清理：
  - 已实施完成 → completed
  - 已失效/重复 → 删除
  - 未完成 → 写明阻塞原因或下一步
- 最终清单只反映当前任务的真实完成状态

### 效率原则
- 独立操作并行执行（同时读多个文件、并行搜索）
- 文件检索优先用 rg（ripgrep），大幅快于 grep
- 不重复加载已读内容，先检查已有信息
- 核心变更完成后立即汇报，不做多余建议

### 沟通风格
简明技术中文，偶有英文术语。重要事项先说结论后说论据。复杂变更给出确切文件路径引用。保持有温度的协作感，不沦为说明书式的干巴。

--- project-doc ---

# TradeRadar (原 GatherInfo) — 全球贸易风险情报中枢

## 项目概述

TradeRadar 是一个主题驱动的多源信息采集、标签化入库、统计分析与智能报告生成平台。

| 维度 | 详情 |
|---|---|
| **目标用户** | 跨境贸易情报分析师、海关合规人员 |
| **前端** | React + TypeScript + Vite (rolldown)，端口 5178 |
| **后端** | Python FastAPI + SQLAlchemy 2.0，端口 8109 |
| **数据库** | SQLite（`data/gather.db`），WAL 模式 |
| **启动方式** | `npm run dev` → `scripts/dev.sh` → 同时启动前后端 |
| **Dev Dashboard** | `localhost:9999` 管理所有本地服务 |

---

## 技术栈

### 前端
- `@vitejs/plugin-react` + Vite (rolldown) 构建
- React 18 + TypeScript
- ECharts（仪表盘图表）
- Lucide React（图标库）
- 无路由库：通过 App.tsx 中 `ViewId` 状态驱动视图切换
- **字体**: Inter (英文) + PingFang SC (中文) + JetBrains Mono (代码)
- **设计系统**: 深色主题，CSS 变量体系，4px 步进间距

### 后端
- FastAPI（`app/main.py` 的 `create_app()` 工厂）
- SQLAlchemy 2.0 ORM + SQLite (WAL)
- APScheduler（周期调度）
- httpx（异步 HTTP 客户端）
- BeautifulSoup4（网页解析）
- Pydantic v2（API 校验）

---

## 启动与端口

```bash
# 开发启动
npm run dev
# → backend/.venv/bin/python -m uvicorn ... --port 8109
# → npm run dev (vite) ... --port 5178

# Vite 开发服务器
# 前端: http://localhost:5178
# proxy: /api/* → http://127.0.0.1:8109
# proxy: /health → http://127.0.0.1:8109

# 生产构建
npm run build    # 在 frontend/dist/ 输出
```

### 其他启动方式
- `python3 startup.py` — 通过 `subprocess` 拉起前后端
- `python3 run_backend.py` — 仅启动后端（8109 端口）
- Dev Dashboard (`localhost:9999`) — 启停按钮管理全部服务

---

## 数据模型（SQLAlchemy）

### 核心实体

```
SourceConfig (信息源) ──< CollectionRun (采集执行) ──< CollectedItem (采集条目) >── Tag (标签)
        Topic (主题)    ──< CollectionRun
```

### 表结构

| 表名 | 用途 | 关键字段 |
|---|---|---|
| `topics` | 采集主题定义 | id, name, keywords, source_ids, schedule_cron, collect_window_days, auto_report, auto_tag_rules, keyword_tags, description_prompt |
| `source_configs` | 信息源配置 | id, name, channel (枚举), base_url, api_key, auth_config, rate_limit_rps |
| `collection_runs` | 每次采集的执行记录 | source_id, topic_id, status, items_new, batch_id, window_start/end, error_log |
| `collected_items` | 采集到的单条信息 | source_id, run_id, topic_id, title, content, url, language, category, tags (M:N), quality_score |
| `tags` | 标签系统 | id, namespace, value, color, item_count (M:N 关联 CollectedItem) |
| `reports` | 自动生成的报告 | topic_id, title, content, status, model_id, item_ids, collection_run_id |
| `model_configs` | AI 模型配置 | id, provider, base_url, api_key, model_name, is_default |
| `schedule_configs` | 全局调度配置 | cron_expression, source_ids, topic_ids |
| `system_config` | 单行全局设置 | report_title_format, report_output_dir, report_formats |

### SourceChannel 枚举
`official` · `rss` · `commercial` · `web_scrape` · `api_search` · `json_api` · `social` · `deepweb` · `manual`

### JobStatus 枚举
`pending` · `running` · `completed` · `failed` · `partial`

### ItemStatus 枚举
`raw` → `tagged` → `enriched` → `archived` · `discarded`

---

## 后端架构

### 文件结构（17 文件，5998 行）

| 文件 | 行数 | 职责 |
|---|---|---|
| `main.py` | 261 | FastAPI 应用工厂、CORS、限流中间件、lifespan 调度器启动 |
| `collection_routes.py` | 2227 | **全部 API 路由**：源/主题/采集/条目/标签/模型/报告/设置 |
| `collection_schemas.py` | 568 | Pydantic 请求/响应模型（TopicCreate, TopicOut, BatchOut 等） |
| `engine.py` | 289 | **采集引擎**：采集编排、去重持久化、自动打标签、批次分组 |
| `report_engine.py` | 329 | 智能报告生成：构建提示词 → 调用 LLM → 持久化 + 导出 |
| `report_export.py` | 244 | 报告导出（MD/HTML/DOCX/PDF） |
| `scheduler.py` | 126 | APScheduler 集成：主题调度 + 自动报告触发 |
| `stats_routes.py` | 136 | 仪表盘统计、每日趋势、分类/语言/来源分布 |
| `models.py` | 516 | SQLAlchemy ORM 模型定义 |
| `models_additions.py` | 153 | 运行时 Schema 迁移（`ALTER TABLE ADD COLUMN`） |
| `database.py` | 115 | SQLAlchemy 引擎、会话工厂、DB 备份 + 一致性检查 |
| `services.py` | 216 | 配置导出/导入（全部模型的 JSON 序列化） |
| `seed_demo_data.py` | 351 | 默认数据：自带 16 个信息源 + 2 个主题 + 关键词模板 |
| `data.py` | 287 | Demo 数据加载 |
| `schemas.py` | 179 | 旧的 Pydantic 模型（部分被 collection_schemas 取代） |

### 采集引擎流程（engine.py）

```
collect_topic(topic_id)
  → 解析 Topic（keywords, source_ids, collect_window_days）
  → 生成 batch_id（同次执行的所有来源共享）
  → 并行调用 collect_from_source() 每个关联来源
    → 创建 CollectionRun
    → ConnectorRegistry.create(source) → connector.fetch(keywords)
    → _persist_items() → 关键词过滤 + 窗口过滤 + 去重入库
  → _apply_auto_tags() → 根据 auto_tag_rules 自动打标签
  → 更新 Topic.last_run_at / total_items_collected
  → 触发自动报告（如 auto_report=True）
```

### 连接器系统（8 文件）

| 文件 | 注册频道 | 用途 |
|---|---|---|
| `base.py` | — | 抽象基类 `BaseCollector`、`FetchItem`、`CollectResult`、`ConnectorRegistry` |
| `tavily_search.py` | `api_search` | **Tavily Web Search API** (默认搜索引擎, 生产主力) |
| `rss_collector.py` | `rss` | RSS/Atom 订阅源采集 |
| `web_scrape.py` | `web_scrape` | 结构化网页抓取（CSS 选择器 + BS4 解析） |
| `official_api.py` | `official` | 官方 API：WTO ePing / EUR-Lex / 中国海关 / MOFCOM / UN Comtrade |
| `search_engines.py` | `api_search` | **搜索分发器**：根据 auth_config.search_type 路由到 Baidu/Bing/360/Tavily |
| `json_api.py` | `json_api` | 通用 JSON API 直连（NewsAPI 等） |

---

## 前端架构

### 组件结构（13 组件，3263 行）

| 组件 | 行数 | 功能 |
|---|---|---|
| `App.tsx` | 81 | 导航框架（13 个菜单项）、侧边栏、视图路由 |
| `TopicsPage.tsx` | 499 | **主题管理**：CRUD + 关键词模板推荐 + 多选信息源下拉 + 采集/报告 |
| `ModelConfigPage.tsx` | 402 | AI 模型配置：添加/编辑/测试/自动发现/设为默认 |
| `ItemsPage.tsx` | 363 | 采集条目浏览：搜索/过滤/分页/全文阅读/批量选择删除 |
| `SchedulesPage.tsx` | 375 | 周期调度管理：频率选择器/Cron 预览/主题绑定 |
| `ReportsPage.tsx` | 360 | 智能报告：生成/查看/导出/批量生成/Markdown 渲染 |
| `TagsPage.tsx` | 364 | 标签系统：按命名空间管理/统计/合并/M:N 关联 |
| `SettingsPage.tsx` | 254 | 系统配置：配置导出/导入/报告设置 |
| `SourcesPage.tsx` | 261 | 信息源管理：CRUD/连接验证/渠道选择 |
| `HistoryPage.tsx` | 134 | 采集历史：活跃任务实时追踪 + 已完成批次展开查看 |
| `DashboardPage.tsx` | 160 | 仪表盘概览：ECharts 统计图表 |
| `EChart.tsx` | 44 | ECharts React 封装 |
| `ErrorBoundary.tsx` | 47 | React 错误边界 |
| `AppLogo.tsx` | 150 | **TradeRadar 品牌 Logo（SVG + 动画）** |
| `IntelligenceHomePage.tsx` | 433 | **情报主页**：新闻流 + 报告摘要 + 活跃主题 |

### 核心文件

| 文件 | 行数 | 用途 |
|---|---|---|
| `api.ts` | ~220 | **API 客户端**：全部 35+ 个接口的 `get/post/put/del` 封装 |
| `types.ts` | ~200 | TypeScript 类型定义：Source, Topic, BatchOut, ActiveRunOut 等 |
| `styles.css` | ~370 | **设计系统 CSS 变量 + 全组件样式（深色主题 v2.0）** |
| `templates.ts` | 98 | 关键词模板 + 描述提示词模板（10+5 个预设） |

### 设计系统 v2.0（品牌重塑后）

- **品牌名**: TradeRadar（技术代号 GatherInfo）
- **品牌标语**: 感知全球贸易脉搏，洞察政策风险先机
- **深色主题**: CSS 变量体系（`--ink`, `--surface`, `--accent`, `--line` 等）
- **背景层次**: 5 层（surface-deep → surface → surface-elevated → surface-card → surface-hover）
- **文字层次**: 4 级（ink → ink-secondary → ink-muted → ink-subtle）
- **发光效果**: accent-glow, green-glow（用于卡片 hover）
- **间距**: 4px 步进（4/8/12/16/24/32/48）
- **圆角**: `--radius: 8px`
- **字体**: Inter → SF Pro Display → PingFang SC → system-ui
- **响应式**: 768px 断点切换侧边栏宽度 + 简化布局
- **Logo**: 雷达信号波 SVG 动画（三层波纹扩散 + 扫描线旋转 + 中心脉冲发光）

---

## API 概览

所有 API 前缀为 `/api/v1`。

### 核心资源路由

| 方法 | 路径 | 功能 |
|---|---|---|
| GET/POST | `/sources` | 列表/创建信息源 |
| GET/PUT/DELETE | `/sources/{id}` | 获取/更新/删除 |
| POST | `/sources/{id}/validate` | 测试连接 |
| GET/POST | `/topics` | 列表/创建主题 |
| GET/PUT/DELETE | `/topics/{id}` | 获取/更新/删除 |
| POST | `/collect` | 执行采集（按 topic_id 或 source_id） |
| GET | `/items` | 条目列表（支持 topic/source/tag/language/q/run_id 过滤） |
| GET | `/items/{id}` | 单条详情 |
| GET | `/items/ids` | 匹配条目的 ID 列表（用于全选） |
| POST | `/items/batch-delete` | 批量删除 |
| GET | `/runs` | 采集执行记录 |
| GET | `/runs/batches` | 按 batch_id 分组的批次历史 |
| GET | `/runs/active` | 当前正在执行的任务 |
| GET/POST | `/models` | AI 模型 CRUD |
| POST | `/models/{id}/test` | 测试连接 |
| POST | `/models/{id}/list-models` | 列出可用模型 |
| POST | `/models/auto-discover` | 自动发现本地模型服务 |
| GET/POST | `/reports` | 报告列表/生成 |
| GET/DELETE | `/reports/{id}` | 查看/删除报告 |
| POST | `/reports/batch-generate` | 批量生成 |
| POST | `/reports/{id}/export` | 导出文件 |
| GET | `/reports/{id}/download` | 下载文件 |
| GET | `/tags` | 标签列表 |
| POST | `/tags/merge` | 标签合并 |
| GET | `/settings` | 系统设置 |
| GET | `/stats/dashboard` | 仪表盘统计 |

---

## 调度系统

### 主题级别调度（推荐方式）
在主题编辑表单中：
1. Cron 表达式 → 设定执行频率（如 `0 8 * * *` = 每日 8 点）
2. 采集时间范围（天数）→ 限制发布时间窗口
3. 自动报告 → 采集完成后自动生成分析报告

调度名称自动生成格式：`主题名_频率_信息`

### 全局调度（SchedulesPage）
传统方式：绑定多个主题 + 信息源 + Cron 表达式，更灵活但更复杂。

### 自动报告触发
- 手动采集后触发（`POST /collect` 返回前 fire-and-forget）
- 定时调度触发（`scheduler._run_topic()` 中同步 await）

---

## 重要约定与陷阱

### 端口一致性
- **后端始终用 8109**：`scripts/dev.sh`、`vite.config.ts`、`startup.py`、`run_backend.py` 必须一致
- 之前 dev.sh 使用 8108 导致 Vite proxy 502 Bad Gateway（已修复）

### 数据不可变
- 前端 state 更新必须用展开运算符（`{...obj, key: val}`）
- 直接修改 `obj.name = x` 会导致不可预测的 bug

### 研发约束
- 函数 ≤50 行，文件 ≤400 行（极限 800）
- 嵌套 ≤3 层
- TDD 循环（RED → GREEN → IMPROVE），覆盖率 ≥80%
- 提交格式：`<type>: <描述>`（feat/fix/refactor/docs/test/chore/perf/ci）
- API 中英文标点容错（中文逗号/冒号统一归一化为英文）
- `apply_patch` 格式要求首行 `*** Begin Patch`

### 其他注意
- SQLite 不支持并发写入（FastAPI 单进程已足够）
- `uvicorn` 的 `--factory` 标志因为 `create_app` 是工厂函数
- `.dev-pids` 文件用于 Dev Dashboard 停止时清理子进程
- `models_additions.py` 在每个 `init_db()` 时运行，自动添加缺失列
- 报告渲染依赖 WeasyPrint（PDF）/ Pandoc（DOCX），缺失时不阻塞

---

## 品牌重塑记录（2026-06-27）

### 变更内容
1. **品牌名**: GatherInfo → TradeRadar（中文：智讯）
2. **Logo**: 新设计雷达信号波 SVG 动画（`frontend/src/components/AppLogo.tsx`）
3. **标题**: "全球贸易情报平台" → "全球贸易风险情报中枢"
4. **标语**: 新增 "感知全球贸易脉搏，洞察政策风险先机"
5. **配色**: 升级设计系统 v2.0，增加背景/文字层次、发光效果
6. **字体**: 引入 Inter + JetBrains Mono，建立字号/字重系统
7. **favicon**: 新增 SVG 格式 favicon（`frontend/public/favicon.svg`）
8. **后端**: 更新 API title/description/version

### 相关文件
- `frontend/src/components/AppLogo.tsx` — 新 Logo 组件
- `frontend/src/App.tsx` — 品牌名引用更新
- `frontend/src/components/IntelligenceHomePage.tsx` — 标题/标语更新
- `frontend/src/styles.css` — 设计系统 v2.0
- `frontend/index.html` — 标题/meta/favicon
- `frontend/public/favicon.svg` — 新 favicon
- `backend/app/main.py` — API 品牌信息
- `backend/app/seed_demo_data.py` — 品牌名引用

---

## 6/30 优化记录

### 变更内容
1. **品牌名**: TradeRadar → RiskInfoRader
2. **情报主页**: 右侧新增手动采集弹窗（选择主题）和最近一周报告弹窗，并提示用户自动清理策略
3. **报告清理**: 后端 `report_service.py` / `routes/reports.py` / `scheduler.py` 支持按 `days` 清理，默认保留最近 7 天
4. **主题信息源选择**: 新建主题时使用 `SourceSelector` 复选集合，复选框在条目左侧
5. **导入网址配置**: 修复 `import_external_sources.py` 与 `models_additions.py`，导入的网址不再被标记为“待配置”
6. **信息源分组**: `SourcesPage.tsx` 默认折叠，L1/L2 分组名称映射为中文
7. **时间窗口过滤**: `engine.py` 的 `_persist_items` 严格跳过无日期或超窗条目，并新增 `_extract_date_from_text` 从文本提取日期
8. **采集条目折叠**: `ItemsPage.tsx` 按主题 + 批次折叠显示，筛选后仍按折叠方式呈现
9. **通知精简**: 后端 `notification_models.py` 跳过空成功通知，新增 `send_single`；`routes/notifications.py` 新增 `/prune` 并修复测试通知单发
10. **通知前端**: `NotificationsPage.tsx` 支持隐藏测试/重复通知，新增“显示全部/清理测试通知”按钮和隐藏提示

### 相关文件
- `frontend/src/App.tsx` — 左上角品牌名
- `frontend/index.html` — 标题/meta
- `frontend/src/components/HomeHero.tsx` — 品牌名
- `frontend/src/components/HomeActionDialogs.tsx` — 采集/报告弹窗
- `frontend/src/components/IntelligenceHomePage.tsx` — 接入弹窗
- `backend/app/report_service.py` — 报告清理
- `backend/app/routes/reports.py` — 清理路由
- `backend/app/scheduler.py` — 定时清理
- `frontend/src/components/TopicForm.tsx` / `SourceSelector.tsx` — 主题信息源选择
- `backend/app/import_external_sources.py` / `models_additions.py` — 导入网址配置
- `frontend/src/components/SourcesPage.tsx` — 信息源分组折叠
- `backend/app/engine.py` — 时间窗口过滤
- `frontend/src/components/ItemsPage.tsx` — 条目折叠
- `backend/app/notification_models.py` / `routes/notifications.py` — 通知精简
- `frontend/src/components/NotificationsPage.tsx` — 通知前端精简
- `frontend/src/api.ts` — `pruneNotifications`

### 验证
- `npm run build` 通过
- `npm run dev` 前后端正常启动，前端 `localhost:5178`、后端 `localhost:8109/health` 均可用

---

## 2026-07-26 素材集与下游分析衔接

### 核心约定
1. `MaterialSet` 是不可变的信息成员快照；相同主题、报告和条目组合复用同一素材集。
2. 每次发送到 YMG-Deep 或 HaiSee 都写入独立 `HandoffRun`，不得覆盖此前会话或任务记录。
3. YMG-Deep 接收 `risk-intelligence-material-set/v1`，将结构化素材保存为会话输入，阶段报告仅作为分析线索。
4. HaiSee 每条采集信息对应一个独立转译分析任务；超过 50 条时由 GatherInfo 自动拆成多个批次。
5. 报告分为 `analytical`（总结推理分析型）和 `archive`（逐条信息归档型）。归档型保留全部条目的完整中文正文，不进行跨条目事实合并。
6. 搜索采集必须严格执行主题发布日期窗口；无可核验日期或超窗的条目不得入库。
7. 关键词是语义方向，不是逐字匹配条件；AI 模型信息源应生成语义检索计划，并可独立于指定网站开展广泛采集。

### 验证基线
- GatherInfo 后端：`backend/.venv/bin/python -m pytest backend/tests -q`
- GatherInfo 前端：`npm --prefix frontend run build`
- 信息源树交互：`node frontend/_test_selector.mjs`
- YMG-Deep 素材接收：`.venv/bin/python -m pytest backend/tests/test_input_materials.py backend/tests/test_config_export_import.py -q`
- HaiSee 批量任务：项目后端全量 pytest，保持覆盖率门禁通过

---

## 2026-07-26 配置弹窗工作区规范

1. 新建或编辑信息源、模型、主题、调度、采集类别、标签等配置表单，统一使用
   `modal modal--config`。
2. 桌面端配置弹窗占用约 `75vw × 78vh`（并设置最大值），标题和操作区固定，
   仅表单内容区域滚动；不得出现整窗横向滚动。
3. 配置表单默认使用两列自适应布局，窄屏自动切换为单列、近全屏工作区。
4. 确认、提示、阅读详情等非配置弹窗保持紧凑尺寸，不套用 `modal--config`。
5. 调整配置界面后至少执行 `npm --prefix frontend run build` 验证。

---

## 2026-07-26 实时采集进度规范

1. 所有采集入口统一经过 `CollectionEngine`，运行过程写入
   `CollectionRun.progress_events`，不得只在前端模拟进度。
2. 进度事件至少覆盖：任务准备、连接、检索、候选发现、时间窗口核验、质量审核、
   去重入库、中文转译与内容整理、完成或失败。
3. 顶部 `CollectionActivityIndicator` 每 2 秒读取活动任务；手动采集通过
   `collection-started` / `collection-finished` 事件即时反馈，周期任务由轮询自动发现。
   “查看进度”使用主工作区右侧常驻 panel，不使用弹窗或遮罩；panel 打开时主内容必须自适应让位。
4. 配置表单必填项统一使用 `field-label-row` + `required-mark`，星号与字段名同行，
   对应输入控件同时设置原生 `required` 属性。
5. 实时进度事件采用不可变列表追加并限制数量，单次运行最多保留 120 个节点。
6. 顶部工作栏在工作区滚动时保持固定；采集中轮换显示“全网搜集、智能处理、服务战略”，
   文字使用随机颜色及随机进出方向，并提供 reduced-motion 降级。

---

## 2026-07-26 首页情报与统计口径

1. “今日采集”和每日趋势按北京时间自然日计算，条目列表按 `collected_at` 倒序展示，
   确保顶部数字、仪表盘和“最新采集信息”口径一致。
2. 重点情报由后端从最近 10 天候选中评估中国海关监管、风险防控、出口管制、
   对华贸易影响和内容完整性，默认展示 3 条。
3. 重点情报 ID 持久化在 `SystemConfig.featured_item_ids`；没有新的合格内容时保持原选择，
   不因普通新入库信息造成首页重点内容抖动。
4. 测试写入正式开发库时必须在 `finally` 或模块 teardown 中精确清理，禁止遗留测试条目
   污染仪表盘统计；清理历史污染前必须先备份数据库。

---

## 2026-07-27 信息源可用性与诊断规范

1. 标签 `item_count` 是 `item_tags` 的缓存值；标签列表、标签统计和仪表盘展示前必须用
   `refresh_tag_counts()` 按关联表核对，禁止直接相信历史缓存。
2. 信息源是否“可采集”按最低可行配置判断：公开网页、RSS、官方、社交和深网渠道必须有
   有效采集地址；搜索 API、JSON API、商业接口和 AI 提示检索必须具有服务凭据。不得因更新、
   迁移或种子数据重置、添加或覆盖用户的模型配置。
3. “AI 模型信息源”仅复用已生效模型，承担语义检索规划、中文转译和质量审核；网站、RSS、
   搜索 API 仍负责返回可核验的原始信息和源链接。AI 不替代原始证据渠道。
4. 静态 API 路径必须定义在同前缀动态路径（如 `/sources/{source_id}`）之前，避免
   `405 Method Not Allowed`。`/sources/reconcile-readiness` 专门用于重新核查历史导入来源。
5. 主题编辑的信息源选择器以两层树展示，二层条目应在展开时条件渲染，不能依赖 `hidden`
   属性；一级复选框可批量选择，叶子节点可单独选择。
6. 采集进度的失败数量支持双击诊断。`/runs/failures` 应按错误类型给出修复、停用或删除建议，
   同时保留原始技术错误供核验；访问拒绝（403/406）优先于错误页 URL 中的 404 文字判断。

---

## 2026-07-27 夜间全主题采集稳定性规范

1. 模型辅助采集必须限制单来源候选量（`MAX_CANDIDATES_PER_SOURCE=9`）并采用
   `SOURCE_COLLECTION_CONCURRENCY=4` 的受控并发；每个来源整体执行超过 90 秒应记录失败并
   继续队列，不能因慢网页永久阻塞其他主题。
2. 已启用来源使用稳定限额：网页/社交每轮 4 条、RSS 12 条、Tavily 12 条；原始来源链接仍要
   保留，候选信息通过 LLM 审核后再入库。限额可由 `SourceUpdate.max_items_per_run`、
   `timeout_seconds` 和 `max_retries` 调整。
3. `backend/scripts/run_topic_queue.py` 是无人值守的顺序采集器。它为每个主题创建独立 DB 会话，
   等待同主题已有运行结束，并支持 `--only-original`、`--skip-topic` 以恢复未完成队列。
4. 夜间稳定性测试确认无凭据、404/403、非 RSS、SSL 或来源超时的渠道，应先停用并写明原因，
   不删除来源定义和历史条目；修复地址、凭据或访问策略后再由用户重新启用。
5. 新建的风险主题均绑定已存在的 `ollama_cloud / glm-5.2`，采集窗口为 30 天。模型负责检索
   语义规划、文章独立性/完整性审核、海关价值评估与中文整理；Tavily 负责提供原始网页链接。
