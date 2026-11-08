# 面试情景模拟训练与话术优化系统

本科毕业设计项目。系统通过大模型、LangGraph 状态机和四维评分，完成以下训练闭环：

**想按步骤启动？双击打开 [`docs/启动指南.md`](docs/启动指南.md)。** 页面离线可用，优先指导你在 PyCharm 和 Docker Desktop 中点按钮操作；仅在功能不可用时才用备用命令。

**岗位/行业面试场景 → AI 角色多轮追问 → 四维评分 → 生成带编号的提升计划（原场景再练 + 视频面试 + 复盘批注 + 个性化微课）→ 再练一轮并对比分数**。话术优化是独立功能，可将自己的原话改写成三种风格并对比收藏。

## 技术栈

- 后端：Python 3.10+、FastAPI、SQLAlchemy、LangGraph、SSE
- 前端：Vue 3、TypeScript、Vite、Axios、ECharts、PWA 移动端
- 数据库：MySQL
- 状态存储：Redis
- 向量数据库：Milvus；Attu 用于桌面可视化管理
- 大模型：DeepSeek、豆包或通义千问的 OpenAI 兼容 API

项目保留 SQLite、内存状态和本地教练模板作为断网兜底，但正式演示建议使用 MySQL、Redis、
Milvus 和真实大模型 Key，以对应开题报告中的技术栈。

## 一、准备环境

需要安装：

- Python 3.10 或更高版本；
- Node.js；
- Docker Desktop；
- Attu Desktop（用于查看 Milvus，可选启动，不影响系统运行）。

复制环境变量模板：

```powershell
Set-Location D:\graduation_design
Copy-Item .env.example .env
```

打开 `.env`，把下面一项替换为自己的大模型 Key：

```dotenv
LLM_API_KEY=你的Key
```

默认配置使用 DeepSeek：

```dotenv
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

Key 不能提交到 Git，也不要写进 Python 或 Vue 源码。

## 二、启动 MySQL、Redis 和 Milvus

在项目根目录执行：

```powershell
docker compose --project-name career-coach up -d
docker compose --project-name career-coach ps
```

Milvus 会自动启动它依赖的 etcd 和 MinIO。第一次下载镜像会比较慢，`mysql`、`redis`、`milvus`
显示为 `healthy` 后再启动后端。

本机 Docker MySQL 映射到 `3308`、Redis 映射到 `6380`；`3307` 已被另一个项目占用。

桌面 Attu 的连接信息：

```text
Milvus 地址：http://localhost:19530
Token：root:Milvus
```

Attu 只是管理界面，不需要在 Python 中安装。

## 三、启动后端

首次安装依赖：

```powershell
Set-Location D:\graduation_design\backend
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --constraint constraints.txt --requirement requirements-dev.txt
.venv\Scripts\python.exe -m alembic upgrade head
```

启动：

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8081 --reload
```

浏览器打开 `http://127.0.0.1:8081/docs`，能看到接口页面即成功。

在 PyCharm 中可新建 Python 运行配置：

- Module name：`uvicorn`
- Parameters：`app.main:app --host 127.0.0.1 --port 8081 --reload`
- Working directory：`D:\graduation_design\backend`
- Python interpreter：`D:\graduation_design\backend\.venv\Scripts\python.exe`

## 四、启动前端

另开一个终端：

```powershell
Set-Location D:\graduation_design\frontend
npm install
npm run dev
```

访问 `http://localhost:5173`。

想在窄屏上检查布局，可在 Chrome/Edge 按 `F12`，点击设备工具栏的手机图标。

场景卡片现可选“文字对练”或“语音对练”。语音模式采用轮流发言：浏览器识别学员说话、学员核对文字后发送，
后端沿用同一场景对话与四维评分，面试官的文字回复可自动朗读或手动重播。系统不上传或保存录音。

开始面试时可选上传文字版 `.docx` 简历（不超过 2 MB），AI 面试官会按当前面试阶段，围绕简历里明确写出的经历、项目或技术栈提问、追问；不上传仍按原场景训练。原始 Word 文件不会保存，仅提取文字并发送到已配置的大模型；训练页可单独清除简历文字，训练记录页可彻底删除整个会话。

演示账号：

- 学员：`student@example.com` / `Student123!`
- 管理员：`admin@example.com` / `Admin123!`

登录页也可以直接注册新学员。

## 五、答辩演示流程

1. 登录学员账号。
2. 先选行业、岗位，再从适用的 HR 初面、技术一面、技术二面 / 复面、交叉面 / 总监面、HRBP/HR 终面、高管终面中选阶段和难度。不同岗位显示的阶段不一定相同。
3. 进入场景选择文字或语音对练；可选上传 `.docx` 简历体验针对性技术追问。最后一问由学员回答后才收尾；也可在满足最低轮次后选择“答完本题后结束”。
4. 展示内容与逻辑、贴合问题、信息完整、表达干净四维评分及原句证据。
5. 进入“能力提升”按上一场面试类型查看复盘：文字面试是逐轮批注 + 微课；语音面试加对话与表达节奏；视频面试再加镜头表现，然后按计划的场景复练。
6. 打开计划页：先读逐轮复盘批注，再按任务卡完成场景再练、视频面试与个性化微课（可看视频版）。
7. 回到原场景再练一轮，在计划页与报告页对比四维前后分数、提升判定及下一步建议；成长看板和训练记录保留历史。
8. 进入独立“话术优化”页，粘贴自己的原话，生成正式、亲和、简洁三种版本并对比收藏。
9. 用浏览器设备工具栏切到窄屏，检查页面在手机尺寸下的布局（可选）。

评分或话术生成遇到模型不可用时会明确显示降级状态；演示大模型能力前请确认 Key 和模型服务可用。

更简短的现场步骤见 [`docs/毕设演示运行说明.md`](docs/毕设演示运行说明.md)。

## 六、大模型切换

DeepSeek：

```dotenv
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

豆包：

```dotenv
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=火山方舟推理接入点ID
```

通义千问：

```dotenv
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

修改 `.env` 后需要重启后端。没有 Key 或模型接口临时失败时，系统会自动使用本地教练模板，
不会影响基本演示。

## 七、验证项目

后端测试：

```powershell
Set-Location D:\graduation_design\backend
.venv\Scripts\python.exe -m pytest -q
```

前端构建：

```powershell
Set-Location D:\graduation_design\frontend
npm run build
```

性能参数需要验收时，可在后端已启动后运行：

```powershell
$env:LOAD_TEST_EMAIL='student@example.com'
$env:LOAD_TEST_PASSWORD='Student123!'
.venv\Scripts\python.exe scripts\load_test.py --users 20 --output reports\load-test.json
```

## 八、上线部署

生产环境用两个镜像 + 四个容器：`web`（nginx 托管前端并反代 API）、`backend`（uvicorn）、`mysql`、`redis`。

```bash
cp .env.production.example .env      # 填域名、密码、模型 Key
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
python3 scripts/smoke_test.py --base https://your-domain.com
```

- 完整步骤（TLS、备份、升级、回滚、排查）：[`docs/部署指南.md`](docs/部署指南.md)
- 发布前逐项检查：[`docs/上线检查清单.md`](docs/上线检查清单.md)
- 冒烟脚本：`scripts/smoke_test.py`，一条命令检查健康、就绪、登录、场景、训练、评分、报告
- 备份脚本：`scripts/backup.sh`（数据库 + 录像/微课/TTS，默认保留 14 天）

## 目录说明

- `backend/app/features/`：登录、场景、话术、训练、评分、计划和看板业务
- `backend/app/infrastructure/`：大模型、Redis 和 Milvus 接入
- `backend/migrations/`：MySQL 数据库迁移
- `frontend/src/`：Vue 3 页面、组件和接口调用
- `docker-compose.yml`：开发环境 MySQL、Redis、Milvus 及其必要依赖
- `docker-compose.prod.yml`：生产编排（mysql / redis / backend / web）
- `backend/Dockerfile`、`frontend/Dockerfile`、`frontend/nginx.conf`：生产镜像与反向代理
- `scripts/smoke_test.py`、`scripts/backup.sh`：上线冒烟与备份
- `docs/architecture.md`：系统架构说明
- [`docs/技术说明.md`](docs/技术说明.md)：用了哪些模型、分数怎么算、语音与视频怎么接（答辩用）
- `资料_Python版/`：已转换为 Python 技术栈的开题和任务资料
