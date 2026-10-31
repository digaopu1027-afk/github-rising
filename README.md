# 升榜 · GitHub 每日飙升榜

面向中文工具探索者的开源项目发现网站。每日热榜、新秀榜、项目介绍、分类检索与历史记录；不伪造增长或历史曲线。

## 本地使用

需要 Node.js 24+、Python 3.9+。Python 采集器仅使用标准库。

```bash
npm ci
gh auth login
npm run dev
```

已随代码保存首次真实采样的公开导出数据，未配置采集凭证也可以浏览。初始快照不构成增长榜；至少需要相邻两日、相隔 22–26 小时的有效样本。北京时间早上 9 点运行时，若与首次手工采样间隔不足，仍继续观察，直到下一组合格快照产生。

从 GitHub 克隆后，第一次在本地采集前先恢复持久状态（仅在 `.data/` 尚未初始化时运行）：

```bash
git fetch origin data
mkdir -p .data
git archive origin/data | tar -x -C .data
python3 -m collector.collect
```

缺少持久状态而已有公开历史时，采集器会拒绝重新开始，防止误用新基线覆盖原有记录。

检查与构建：

```bash
npm test
npm run check
npm run build
npm run test:site
```

## 数据口径

- 日榜：Star ≥50、净增为正，按净增降序，增长率降序，仓库 ID 升序；最多 50 个。
- 新秀：Star 50～5,000、净增 ≥10，按 `delta / max(previous_stars, 100)` 降序，再按净增降序、ID 升序；最多 20 个。
- 净增为本次 Star 总数减上一次总数，包含新增和取消收藏的共同影响。零基数的实际增长率留空。
- 仅比较北京时间相邻自然日，且间隔须在 22～26 小时。缺失不填零、不插值。
- 同一天重复运行只重新导出已保存档案，不重新取样。档案保存当时的中文介绍、排名和数据。
- 非公开、Fork、归档、禁用及未识别为 OSI 开源许可证的仓库不入榜。许可证列表来自 SPDX `license-list-data`，见 `config/osi-licenses.json`。
- 候选来自 Trending 日榜、周榜和六组搜索。每组默认 20 个候选；每天最多采样 400 个项目，优先当天发现的项目，再继续既有追踪。超额项目保留历史但当天不排名，不算作零增长。这个默认值为 Actions 自带凭证每仓库每小时 1,000 次请求的限额预留余量。不是全 GitHub 完整榜单。
- `--per-query` 可调整每组搜索数量（最多 100）；`--max-repos` 可调整每日采样预算，设 0 不限制。调大前注意 API 限流。

## 内容来源与模型

初始中文介绍在 `config/editorial.json`，每条均有来自官方描述的原文依据；原文不再匹配时自动失效。模型结果同样必须返回并通过精确原文片段检查。该检查证明出处存在，不能保证摘要所有判断都正确。

可设置以下环境变量（不写入浏览器，不提交密钥）：

| 名称 | 用途 |
| --- | --- |
| `GITHUB_TOKEN` | 读取公开仓库；本地未设置时使用 `gh auth token` |
| `LLM_API_KEY` | 兼容 OpenAI 的模型密钥 |
| `LLM_BASE_URL` | HTTPS API 根地址，默认 `https://api.openai.com/v1` |
| `LLM_MODEL` | 服务支持的模型名称；不设置则不调用模型 |

仅来源变化时生成新内容；未配置模型、调用失败或证据不符时保留原始描述，并显示“中文说明待补充”。无密钥不影响榜单采集。

## 自动更新与部署

代码在 `main`，持久数据在独立 `data` 分支。首次设置必须将 `.data/` 中的真实状态推送到 `data` 分支根目录；这个分支至少需要一个初始提交。不要把它放在 `main` 的嵌套目录。

GitHub Pages 的 Source 选择 **GitHub Actions**。工作流 `.github/workflows/daily.yml` 在北京时间 09:00 触发，也可在 Actions 页面手动运行；定时可能延迟。仓库需允许 Actions 写入 contents 和部署 Pages。

仓库 Secrets 配置 `LLM_API_KEY`，Variables 配置 `LLM_BASE_URL` 和 `LLM_MODEL`，无需为采集额外配置 GitHub 密钥。未设置 LLM 仍正常采集。Pages 默认公开，不需要站点账户或数据库。

运行流程：拉取代码与数据分支 → 测试 → 导出最近档案 → 采集 → 先提交数据状态 → 类型检查与构建 → 发布。数据推送失败时停止发布，避免发布不可持久恢复的观察。采集失败时仍发布上份有效记录与失败提示，并把运行标记为失败。GitHub Actions 的错误状态与日志是首版运维入口。

部署配置通过 `SITE_URL` 和 `BASE_PATH` 提供；工作流自动使用仓库拥有者和仓库名称，支持 `/github-rising/` 子路径。数据分支是历史数据源，不应删除；无需从 README 或第三方事件中回填历史。

## 目录与公开数据

`collector/`：采集、证据校验、排名和不可变归档。`src/`：Astro 网站。`.data/`：本地持久状态（不提交到主分支）。`public/data/`：不含密钥的静态导出。

- `latest.json`：最新一期完整榜单、项目观察和发现来源。
- `status.json`：最近尝试状态 `ok / partial / failed` 与时间。
- `history/index.json`、`history/YYYY-MM-DD.json`：历史索引与当日冻结档案。
- `projects/index.json`、`projects/{GitHub ID}.json`：最新项目介绍与真实采样序列。

项目详情的历史 URL 为 `/history/{date}/{id}/`，保留当天介绍并只显示截至当天的采样，避免从历史页面跳进现在的介绍。

## 验证边界

单元测试覆盖统计区间、门槛、并列、负增长、许可证、改名、漏采、冷启动、证据校验、重复运行及历史冻结。网站包含数据积累、空榜、过滤无结果、失败、部分成功与超过 30 小时未更新的状态。

完整每日流程的验收需要两个相隔 22–26 小时的真实采样。一次开发会话中的即时重跑只验证幂等性，不算第二天的数据。部署记录见 `VALIDATION.md`。

`python3 tests/build_fixture.py` 可在系统临时目录生成标有“禁止发布”的隔离测试站，用于验证有排名和两点曲线的界面。它不会修改真实状态、`public/data/` 或生产 `dist/`。`PUBLIC_DIR` 仅用于选择隔离的构建输入，生产工作流不设置该变量。
