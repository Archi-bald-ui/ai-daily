# AI Daily

每日 AI 资讯精选，自动抓取 + AI 评分筛选。

## 功能

- 每天 08:00 CST 自动从 11 个信源抓取最新资讯
- MiniMax AI 对每篇文章进行重要性打分（1-10）
- 达到阈值（≥7）才入选，每类最多 3 篇
- 支持分类筛选、关键词搜索、日期切换
- 保留最近 30 天数据

## 信源

| 分类     | 信源                                            |
| -------- | ----------------------------------------------- |
| 技术博客 | OpenAI Blog, Google AI, HuggingFace, Anthropic  |
| 新闻资讯 | The Verge AI, TechCrunch AI, Ars Technica       |
| 论文     | arXiv cs.AI, arXiv cs.CL                        |
| 中文资讯 | 机器之心, 量子位                                |

## 部署步骤

### 1. 创建 GitHub 仓库

```bash
cd ai-daily
git init
git add .
git commit -m "init"
```

在 GitHub 上新建仓库，然后：

```bash
git remote add origin https://github.com/<你的用户名>/ai-daily.git
git branch -M main
git push -u origin main
```

### 2. 配置 Secrets

进入仓库 → Settings → Secrets and variables → Actions：

- 添加 Secret: `MINIMAX_API_KEY` = 你的 MiniMax API Key
- （可选）添加 Variable: `MINIMAX_MODEL` = 模型名称（默认 `MiniMax-M2.7`）

### 3. 启用 GitHub Pages

进入仓库 → Settings → Pages：

- Source: **Deploy from a branch**
- Branch: `main`，目录: `/docs`
- Save

等待几分钟后，访问 `https://<用户名>.github.io/ai-daily/` 即可。

### 4. 首次手动运行

进入仓库 → Actions → Daily AI News Fetch → Run workflow

这会立即抓取一次数据，验证流程是否正常。

## 本地预览

```bash
cd docs
python -m http.server 8000
```

打开 http://localhost:8000 查看效果（已内置示例数据）。

## 自定义

### 修改信源

编辑 `scripts/fetch.py` 中的 `SOURCES` 列表。

### 修改筛选规则

- `SCORE_THRESHOLD`: 入选分数阈值（默认 7）
- `MAX_PER_CATEGORY`: 每类最大篇数（默认 3）
- `DATA_KEEP_DAYS`: 数据保留天数（默认 30）

### 修改定时

编辑 `.github/workflows/daily.yml` 中的 cron 表达式。

## 技术栈

- 前端：纯 HTML / CSS / JS，无构建工具
- 数据：GitHub Actions 定时抓取 → JSON 文件
- AI：MiniMax API（Anthropic 兼容格式）
- 部署：GitHub Pages（免费）
