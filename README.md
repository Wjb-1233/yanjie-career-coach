# 面试情景模拟训练与话术优化系统

本科毕业设计项目。系统通过大模型、LangGraph 状态机和五维评分，完成以下训练闭环：

**想按步骤启动？双击打开 [`docs/启动指南.html`](docs/启动指南.html)。** 页面离线可用，优先指导你在 PyCharm 和 Docker Desktop 中点按钮操作；仅在功能不可用时才用备用命令。

**岗位/行业面试场景 → AI 角色多轮追问 → 五维评分 → 最薄弱维度推荐基础能力场景 → 专项对练 → 原场景复测与评分对比**。话术优化是独立功能，可将自己的原话改写成三种风格并对比收藏。

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

登录后点击左侧“下载安卓 App”，即可取得可安装的安卓测试版 APK；也可直接下载
[`android-app/言阶-安卓测试版.apk`](android-app/言阶-安卓测试版.apk)。安装和局域网连接方法见
[安卓 App 安装与连接](docs/安卓App安装与连接.md)。若只想在电脑上查看手机布局，
可在 Chrome/Edge 按 `F12`，点击设备工具栏的手机图标。

场景卡片现可选“文字对练”或“语音对练”。语音模式采用轮流发言：浏览器识别学员说话、学员核对文字后发送，
后端沿用同一场景对话与五维评分，面试官的文字回复可自动朗读或手动重播。系统不上传或保存录音；
这不是双方同时说话的实时电话。安卓 APK 通过同一局域网连接电脑，使用系统语音识别并请求麦克风权限；
若直接用手机浏览器打开网页，局域网 HTTP 可能无法调用浏览器语音识别，通常需要 HTTPS。

开始面试时可选上传文字版 `.docx` 简历（不超过 2 MB），AI 面试官会按当前面试阶段，围绕简历里明确写出的经历、项目或技术栈提问、追问；不上传仍按原场景训练。五维通用练习不需要简历。原始 Word 文件不会保存，仅提取文字并发送到已配置的大模型；训练页可单独清除简历文字，训练记录页可彻底删除整个会话。安卓 App 的简历按钮会打开系统文件管理器。

演示账号：

- 学员：`student@example.com` / `Student123!`
- 管理员：`admin@example.com` / `Admin123!`

登录页也可以直接注册新学员。

## 五、答辩演示流程

1. 登录学员账号。
2. 先选行业、岗位，再从适用的 HR 初面、技术一面、技术二面 / 复面、交叉面 / 总监面、HRBP/HR 终面、高管终面中选阶段和难度。不同岗位显示的阶段不一定相同。
3. 进入场景选择文字或语音对练；可选上传 `.docx` 简历体验针对性技术追问。最后一问由学员回答后才收尾；也可在满足最低轮次后选择“答完本题后结束”。
4. 展示逻辑性、得体性、感染力、针对性、简洁度五维评分及原句证据。
5. 进入“能力提升”展示五维通用场景；有报告时再查看最近一次最低分维度，打开对应的针对性模拟场景。
6. 按新生成的两步计划完成至少 6 轮专项对练，再回到原场景完成至少 6 轮复测。
7. 在计划页对比五维初次/复测分数、提升判定及下一步建议；成长看板和训练记录保留历史。
8. 进入独立“话术优化”页，粘贴自己的原话，生成正式、亲和、简洁三种版本并对比收藏。
9. 点击“下载安卓 App”，在同一局域网的安卓手机上访问电脑服务。网页改动由电脑服务器提供，无须重新打包 APK。

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

## 目录说明

- `backend/app/features/`：登录、场景、话术、训练、评分、计划和看板业务
- `backend/app/infrastructure/`：大模型、Redis 和 Milvus 接入
- `backend/migrations/`：MySQL 数据库迁移
- `frontend/src/`：Vue 3 页面、组件和接口调用
- `docker-compose.yml`：MySQL、Redis、Milvus 及其必要依赖
- `docs/architecture.md`：系统架构说明
- `资料_Python版/`：已转换为 Python 技术栈的开题和任务资料
