# COMP7940 项目计划：AutoFigure Telegram Bot

## 背景与目标

本项目要求将实验课中构建的聊天机器人演进为基于 LLM 的**云端部署 Telegram Bot**。
COMP7940 目录中已有一套完整的学术图表生成引擎（`autofigure2.py`）和 FastAPI Web 服务（`server.py`）。

**计划方向**：将 Web 应用**替换为 Telegram Bot**，通过 Telegram 命令暴露图表生成能力。
原有 `autofigure2.py` 将被重构为可导入模块供 Bot 调用（不从根目录抄袭，仅改造 COMP7940 内已有代码）。

- **LLM**：Google Gemini（`google-genai` SDK）
- **数据库**：AWS DynamoDB（云原生，免费 tier）
- **部署**：AWS EC2 t2.micro（免费 tier）+ Docker
- **CI/CD**：GitHub Actions
- **截止日期**：2026 年 4 月 14 日 23:59 | **小组人数**：3 人

---

## 目标架构

```
用户（Telegram）
    │  /generate <论文方法描述>
    ▼
Telegram Bot API
    │
    ▼
Python Bot 应用（AWS EC2 t2.micro，Docker 容器）
├── bot/main.py          ← 启动入口，Telegram polling/webhook
├── bot/handlers.py      ← 命令路由：/start /help /generate /history
├── bot/figure_service.py ← 异步封装 autofigure2.py 的 Gemini 逻辑
└── bot/db.py            ← DynamoDB 读写（boto3）
    │                │
    ▼                ▼
Google Gemini API   AWS DynamoDB（请求日志）
                         │
                    AWS CloudWatch（容器日志 & 监控）
```

---

## Must-Have 需求对照

| 需求 | 实现方式 |
|---|---|
| Telegram 聊天机器人 | `python-telegram-bot` v21+ |
| 云端数据库（日志） | AWS DynamoDB，表 `autofigure_requests` |
| 云平台部署 | AWS EC2 t2.micro（免费 tier） |
| LLM API | Google Gemini（`google-genai`） |
| Git 管理 | GitHub 仓库 + `.gitignore`（不提交 `.env`） |
| 容器技术 | Dockerfile + docker-compose，运行在 EC2 |
| 监控与成本控制 | AWS CloudWatch Logs + AWS Budgets（$5 告警） |

---

## 两个核心功能

### 功能一：文本生成学术图表（`/generate`）

用户发送 `/generate <方法描述文字>`，Bot 调用 Gemini 生成专业学术期刊风格图表，返回 PNG 图片。

**流程：**
1. 用户：`/generate 我们提出一种双编码器注意力架构...`
2. Bot 回复：`正在生成图表，请稍候...`
3. `figure_service.py` 调用 Gemini image generation，使用预定义 prompt 模板
4. Bot 将 PNG 作为图片消息发送给用户
5. `db.py` 将 `{user_id, timestamp, method_text, status, job_id}` 写入 DynamoDB

### 功能二：参考图风格迁移（发图片 + `/generate` 标题）

用户发送一张参考图并在图片标题中写 `/generate <方法描述>`，Bot 提取参考图风格生成风格匹配的学术图表。

**流程：**
1. 用户发送图片，标题为 `/generate <方法描述>`
2. Bot 从 Telegram 下载图片文件
3. `figure_service.py` 将图片 base64 编码后传入 Gemini 风格匹配 prompt
4. Bot 返回风格匹配后的 PNG 图表
5. DynamoDB 日志中包含 `has_reference: true`

**附加拉伸功能**（如时间充裕）：`/history` 命令 — 查询 DynamoDB 返回用户最近 5 次生成记录的摘要。

---

## 目录结构（COMP7940/）

```
COMP7940/
├── bot/
│   ├── __init__.py
│   ├── main.py               ← 启动入口（Telegram Application）
│   ├── handlers.py           ← /start, /help, /generate, /history
│   ├── figure_service.py     ← 异步封装 Gemini 图片生成（不复制根目录代码）
│   └── db.py                 ← DynamoDB boto3 操作封装
├── autofigure2.py            ← 现有引擎，重构 Gemini 部分为可导入函数
├── Dockerfile
├── docker-compose.yml        ← 本地开发 + EC2 多容器部署
├── requirements.txt          ← 新增 python-telegram-bot, boto3
├── .env.example              ← 环境变量模板（不提交真实 key）
├── .github/
│   └── workflows/
│       └── deploy.yml        ← CI/CD：测试 → 构建镜像 → SSH 部署到 EC2
├── infrastructure/
│   └── cloudwatch-config.json
└── plans/
    └── eventual-floating-crown.md  ← 本文件
```

---

## 关键实现说明

### `figure_service.py`（新建，非复制根目录代码）
- 从 **COMP7940 内已有的** `autofigure2.py` 导入 `_gemini_image_generation` 和 `generate_figure`
- 封装为 `async def generate_from_text(method_text: str, api_key: str) -> bytes`
- 封装为 `async def generate_with_reference(method_text, ref_img_bytes, api_key) -> bytes`
- 统一异常处理，返回原始 PNG bytes 给 handler

### `db.py`（新建）
- 使用 `boto3`，EC2 绑定 IAM Role（无需硬编码 credentials）
- DynamoDB 表：`autofigure_requests`
  - Partition key：`user_id`（String）
  - Sort key：`timestamp`（String, ISO-8601）
  - 属性：`method_text`、`has_reference`、`status`、`job_id`
- 函数：`log_request(...)` / `get_user_history(user_id, limit=5)`

### `Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "bot.main"]
```

### `docker-compose.yml`（多容器，展示容器编排）
```yaml
services:
  bot:
    build: .
    env_file: .env
    restart: unless-stopped
    logging:
      driver: awslogs
      options:
        awslogs-group: /autofigure-bot
        awslogs-region: ap-east-1
```

### GitHub Actions `deploy.yml`
触发：push 到 `main` 分支
步骤：
1. `pip install && pytest`（单元测试）
2. `docker build -t autofigure-bot .`
3. SSH 到 EC2 → `docker-compose up -d --build`

GitHub Secrets：`TELEGRAM_TOKEN`、`GEMINI_API_KEY`、`EC2_SSH_KEY`、`EC2_HOST`

---

## Nice-to-Have（加分项）

| 功能 | 实现方式 | 优先级 |
|---|---|---|
| DevOps 工作流 | GitHub Actions CI/CD（测试+自动部署） | 高 |
| 容器编排 | docker-compose 多服务（bot + 可选 redis） | 高 |
| 安全措施 | EC2 IAM Role（不硬编码 key）、GitHub Secrets、`.env` 不入库 | 高 |
| 监控 | CloudWatch Logs 流式日志 + AWS Budgets $5 告警 | 中 |
| 可扩展性 | EC2 Auto Scaling Group（演示策略配置即可） | 低 |
| 负载均衡 | ALB + ASG（时间允许再做） | 低 |

---

## 三人分工建议

| 成员 | 负责内容 |
|---|---|
| 成员 A | Bot 核心：`main.py`、`handlers.py`、Telegram 命令集成 |
| 成员 B | 图表服务：`figure_service.py`、改造 `autofigure2.py` Gemini 路径 |
| 成员 C | 基础设施：Dockerfile、docker-compose、GitHub Actions、EC2 配置、DynamoDB、CloudWatch |

---

## 需要修改的现有文件

| 文件 | 操作 |
|---|---|
| [COMP7940/autofigure2.py](../autofigure2.py) | 重构：将 Gemini 图像生成逻辑提取为独立可导入函数，保留 CLI 入口 |
| [COMP7940/requirements.txt](../requirements.txt) | 新增：`python-telegram-bot>=21.0`、`boto3>=1.34` |

## 需要新建的文件

| 文件 | 用途 |
|---|---|
| [bot/main.py](../bot/main.py) | Bot 启动入口 |
| [bot/handlers.py](../bot/handlers.py) | Telegram 命令处理器 |
| [bot/figure_service.py](../bot/figure_service.py) | 异步 Gemini 封装 |
| [bot/db.py](../bot/db.py) | DynamoDB 操作 |
| [Dockerfile](../Dockerfile) | 容器定义 |
| [docker-compose.yml](../docker-compose.yml) | 本地开发与 EC2 部署 |
| [.github/workflows/deploy.yml](../.github/workflows/deploy.yml) | CI/CD 流水线 |

---

## 端到端验证步骤

1. **本地测试**：`docker-compose up` → Telegram 发 `/start` → 收到欢迎消息
2. **功能一**：`/generate 我们提出一种多尺度注意力网络...` → 约 30 秒内收到 PNG 图表
3. **功能二**：发送参考图片，标题写 `/generate <描述>` → 收到风格匹配的 PNG
4. **数据库**：打开 AWS DynamoDB 控制台 → `autofigure_requests` 表 → 确认有新条目，字段正确
5. **CI/CD**：推送一个无害提交到 `main` → GitHub Actions 全部步骤通过并自动部署
6. **监控**：打开 AWS CloudWatch → 日志组 `/autofigure-bot` → 确认日志实时流入
7. **成本**：打开 AWS Budgets → 确认 $5 告警已配置
