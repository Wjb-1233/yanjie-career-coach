# 系统架构

## 关键决策

1. 采用功能域优先的模块化单体，便于毕业设计演示、测试和后续拆分。
2. Vue 客户端通过版本化 REST API 读写业务数据；AI 回答使用 SSE 流式传输。
3. LangGraph `StateGraph` 将面试过程编排为 `OPENING → DISCOVERY → CHALLENGE → CLOSING → COMPLETED`，对应自我介绍、经历追问、压力追问和收尾，最多 12 轮。
4. DeepSeek、豆包、通义千问通过统一 OpenAI 兼容客户端接入；上游异常时切换本地教练模板。
5. Milvus 通过 `KnowledgeStore` 接口接入；Attu 用于可视化管理同一个 Milvus 实例。
6. 业务数据按用户 ID 隔离，管理员端通过 RBAC 放行。
7. MySQL 保存业务数据，Redis 保存训练状态，Milvus 保存向量知识；SQLite 和内存实现只作为离线兜底。
8. API 使用结构化 JSON 日志和请求 ID，`/ready` 显示各项依赖状态。
9. 移动端采用可安装 PWA，共用 Vue 组件和 FastAPI API；Service Worker 只缓存前端静态资源，明确排除 `/api`。

## 前端组件边界

- `AppShell`：导航、用户状态与路由出口。
- `SceneCard`：只展示场景并发出选择事件。
- `DialoguePanel`：展示消息、输入回答并发出发送/结束事件。
- `ScoreRadar`：只负责五维评分可视化。
- `useTrainingSession`：封装会话创建、SSE 读取和结束训练的副作用。
- `PlanTaskCard`：展示课程、强化训练、改写和复测任务并发出完成事件。
- `useTrainingPlan`：封装计划读取、任务打卡和进度刷新。
- `MobileInstallBanner`：展示 Android 安装入口或 iOS 添加到主屏幕指引。
- `NetworkStatusBanner`：断网时说明离线可用范围。
- `usePwaInstall`：封装安装事件、独立窗口检测和提示关闭状态。
- `useNetworkStatus`：封装浏览器在线/离线事件。
- 路由页只负责组合组件与加载页面数据。

## API

- `POST /api/v1/auth/register|login|refresh|logout`
- `GET /api/v1/scenes`，`POST /api/v1/scenes/{id}/favorite`
- `POST /api/v1/scripts/generate`
- `GET /api/v1/scripts`，`POST /api/v1/scripts/{id}/favorite`
- `POST /api/v1/training-sessions`
- `GET /api/v1/training-sessions`，`GET /api/v1/training-sessions/export`
- `POST /api/v1/training-sessions/{id}/messages`（SSE）
- `POST /api/v1/training-sessions/{id}/finish`
- `GET /api/v1/evaluations/{sessionId}`
- `GET /api/v1/dashboard`
- `GET /api/v1/training-plans/{id}`，`POST /api/v1/training-plans/{id}/tasks/{key}/complete`
- `GET /api/v1/courses`，`POST /api/v1/courses/{id}/progress`
- `GET /api/v1/admin/overview`
- `GET|PATCH /api/v1/admin/users`、`GET|POST|PATCH|DELETE /api/v1/admin/scenes`
- `GET|POST|PATCH|DELETE /api/v1/admin/courses`、`GET /api/v1/admin/sessions`
- `GET /api/v1/admin/learners/{userId}/report` 与个人/全量 CSV 导出
- `POST /api/v1/training-sessions/{id}/archive|restore`、`GET /api/v1/training-sessions?archived=true`
- `DELETE /api/v1/scripts/{id}`；话术版本保存亮点、收藏并支持前端并排对比
- `GET /api/v1/health`（存活检查），`GET /api/v1/ready`（依赖就绪检查）

## 运行拓扑

```text
浏览器/PWA 移动端 → Vue 3 → FastAPI
                              ├─ MySQL
                              ├─ Redis
                              ├─ Milvus → etcd / MinIO（Attu 可视化管理）
                              └─ DeepSeek / 豆包 / 通义千问 API
```

`docker-compose.yml` 负责启动 MySQL、Redis、Milvus 及 Milvus 必需的 etcd、MinIO；前后端仍在
PyCharm 和终端中分别启动，便于答辩展示代码与运行日志。

## 性能验收

`backend/scripts/load_test.py` 使用共享的异步 HTTP 连接池并发创建训练会话、读取 SSE，分别记录响应头、
首个事件、首个 AI token 和完整响应延迟。默认 20 个虚拟用户、首 token p95 门槛 3000ms；任何请求失败、
真实环境发生模型降级或 p95 超标都会返回非零退出码，并生成不含密码和 token 的 JSON 报告。

流式训练接口的认证数据库依赖使用 function scope，在返回 `StreamingResponse` 前完成用户校验并归还连接；
流生成器自行创建短事务会话，避免慢速 SSE 响应长期占用认证连接并耗尽连接池。

