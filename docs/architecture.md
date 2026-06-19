# 合同管理系统 当前架构

## 系统目标与边界

合同管理系统（contract-hub）是一个企业内部合同生命周期管理工具，MVP（0.0.1）覆盖：

- **用户管理**：admin/user 双角色，admin 可管理全部用户
- **合同 CRUD**：合同创建、编辑、删除，五态流转（draft → pending_review → active → expired → terminated）
- **附件管理**：PDF/Word 文件上传下载，类型校验
- **演示环境**：预置演示账号与示例数据

系统边界：企业内部管理工具，不涉及电子签章、第三方合同平台对接、支付等。单机部署，面向小团队（< 50 并发用户）。

## 技术栈与选择理由

### 后端

| 组件 | 选型 | 版本 | 选择理由 |
|------|------|------|----------|
| 框架 | FastAPI | 0.115+ | 异步支持、自动 OpenAPI 文档、Pydantic 类型校验、与 React 前端类型体系一致 |
| 服务器 | Uvicorn | 0.34+ | ASGI 标准，生产可用，单进程满足 MVP 需求 |
| ORM | SQLAlchemy | 2.0+ | Python 生态最成熟的 ORM，2.0 风格声明式映射，与 FastAPI 集成良好 |
| 数据库 | SQLite | 3 | 零配置、文件存储、无需外部服务，MVP 阶段足够；WAL 模式提升并发 |
| 认证 | python-jose + passlib | 3.3+/1.7+ | JWT 标准实现 + bcrypt 密码哈希 |
| 文件校验 | filetype | 1.2+ | 魔数检测，防止扩展名伪装攻击 |

### 前端

| 组件 | 选型 | 版本 | 选择理由 |
|------|------|------|----------|
| 框架 | React | 18 | 最大生态、成熟稳定、社区资源丰富 |
| 构建工具 | Vite | 5 | 开发热更新极快、`base` 配置原生支持子路径部署、构建自动 hash |
| 语言 | TypeScript | 5 | 类型安全，与 Pydantic 模型对应减少接口缺陷 |
| UI 库 | Ant Design | 5 | 最成熟的中文后台管理组件库（Table、Form、Upload、Modal） |
| 路由 | React Router | 6 | `basename` prop 原生支持子路径客户端路由 |
| HTTP | fetch API | 原生 | 零依赖，配合 TypeScript 泛型实现类型安全调用 |

### 部署

| 组件 | 选型 | 说明 |
|------|------|------|
| 进程管理 | systemd | 生产环境进程守护 |
| 反向代理 | Nginx | 公网入口，静态资源缓存，但 HTML 绕过 Nginx 缓存由 FastAPI 下发 |
| 服务器 | Aliyun ECS | 公网 IP 120.24.117.67 |

## 模块职责与依赖

```
contract-hub/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 应用入口，路由注册，中间件，静态文件挂载
│   ├── config.py            # 配置（数据库路径、JWT secret、上传目录）
│   ├── models.py            # SQLAlchemy ORM 模型（User, Contract, Attachment）
│   ├── database.py          # 引擎创建、会话工厂、init_db
│   ├── auth.py              # JWT 生成/验证、密码哈希、get_current_user 依赖
│   ├── routers/             # API 路由模块
│   │   ├── auth_router.py   # /api/auth/*
│   │   ├── users_router.py  # /api/users/*
│   │   ├── contracts_router.py  # /api/contracts/*
│   │   └── attachments_router.py # /api/attachments/*
│   ├── schemas.py           # Pydantic 请求/响应模型
│   ├── seed.py              # 种子数据脚本
│   ├── requirements.txt     # Python 依赖
│   └── uploads/             # 附件存储目录（gitignore）
├── frontend/                # React SPA
│   ├── vite.config.ts       # Vite 配置（base, renderBuiltUrl）
│   ├── tsconfig.json
│   ├── package.json
│   ├── index.html           # SPA 入口
│   └── src/
│       ├── main.tsx         # React 入口
│       ├── App.tsx          # 路由配置 + AuthProvider
│       ├── api/             # API 客户端模块
│       │   └── client.ts    # fetch 封装（base_path, auth header）
│       ├── context/         # React Context
│       │   └── AuthContext.tsx
│       ├── pages/           # 页面组件
│       │   ├── LoginPage.tsx
│       │   ├── DashboardPage.tsx
│       │   ├── UsersPage.tsx
│       │   ├── ContractsPage.tsx
│       │   ├── ContractDetailPage.tsx
│       │   └── ForbiddenPage.tsx
│       └── components/      # 共享组件
│           └── ProtectedRoute.tsx
├── test/                    # 测试
│   ├── test_api/            # pytest 后端测试
│   │   ├── test_auth.py
│   │   ├── test_users.py
│   │   ├── test_contracts.py
│   │   └── test_attachments.py
│   └── smoke.sh             # 冒烟测试脚本
├── docs/                    # 文档
│   ├── architecture.md      # 本文档
│   ├── runbook.md           # 运行手册
│   ├── iterations/          # 迭代文档
│   └── decisions/           # ADR
└── evidence/                # 案卷证据（由 Claude 生成，Hermes 读取）
    └── claude/
```

**模块依赖**：`main.py` → `routers/*` → `auth.py` + `schemas.py` → `models.py` → `database.py`

## 数据流、状态流与外部接口

### 请求数据流

```
Browser (Cache-Control: no-cache 确保获取最新 HTML)
  → Nginx (反向代理，转发到 localhost:19007)
    → FastAPI StaticFiles (/projects/contract-hub/ → frontend/dist/)
      → index.html (Cache-Control: no-cache 响应头)
        → React SPA 加载
          → fetch /projects/contract-hub/api/*
            → FastAPI Router → Auth Middleware → SQLAlchemy → SQLite
```

### 合同状态机

```
                 ┌──────────┐
                 │  draft   │
                 └────┬─────┘
          submit_for_review (user/admin)
                 │
          ┌──────▼──────┐
          │pending_review│
          └──┬──────┬───┘
    reject  │      │  approve
  (admin)   │      │  (admin)
    ┌───────┘      └────────┐
    ▼                       ▼
┌───────┐              ┌────────┐
│ draft │              │ active │
└───────┘              └──┬──┬──┘
                          │  │
               terminate  │  │  auto (定时/手动)
               (admin)    │  │
                     ┌────┘  └──────┐
                     ▼              ▼
              ┌───────────┐  ┌─────────┐
              │terminated │  │ expired │
              └───────────┘  └─────────┘
```

### 角色权限矩阵

| 操作 | admin | user |
|------|-------|------|
| 用户管理 CRUD | ✅ | ❌ |
| 查看全部合同 | ✅ | ❌（仅自己） |
| 创建合同 | ✅ | ✅ |
| 编辑合同 | ✅（全部）| ✅（仅自己的 draft） |
| 删除合同 | ✅（全部）| ✅（仅自己的 draft） |
| 提交审核 | ✅ | ✅（仅自己） |
| 审批/驳回 | ✅ | ❌ |
| 终止合同 | ✅ | ❌ |
| 上传附件 | ✅ | ✅ |
| 下载附件 | ✅ | ✅（关联合同可访问） |
| 删除附件 | ✅ | ✅（自己的附件） |

## 测试策略

- **后端单元/集成测试**：pytest + FastAPI TestClient + 临时 SQLite，覆盖所有 API 端点、认证鉴权、状态机转换、文件类型校验
- **冒烟测试**：shell 脚本（curl）验证 healthz → login → CRUD → upload → download → Cache-Control
- **前端测试**：MVP 阶段手动验证为主（Hermes 浏览器验收），后续迭代引入 Vitest + React Testing Library
- **Hermes 独立验收**：Hermes 运行 pytest 全量 + 启动后浏览器流程验证

## 部署拓扑

```
Aliyun ECS (120.24.117.67)
├── Nginx (port 80)
│   ├── /projects/contract-hub/ → proxy_pass http://127.0.0.1:19007
│   └── 静态资源缓存：非 HTML 文件缓存 1y
└── systemd: codingagent-contract-hub
    └── uvicorn backend.main:app --host 127.0.0.1 --port 19007
        ├── SQLite: /srv/codingagent/contract-hub/contract_hub.db
        └── Uploads: /srv/codingagent/contract-hub/uploads/
```

## 安全边界

- **认证**：JWT Bearer Token，过期时间 24h，密码 bcrypt 哈希（cost=12）
- **授权**：API 层依赖注入校验角色权限
- **文件上传**：魔数检测 + 扩展名双重校验，禁止可执行文件
- **CORS**：仅允许公网域名和本地开发 origin
- **SQL 注入**：SQLAlchemy ORM 参数化查询
- **XSS**：React 默认转义 + CSP 头（后续迭代）
- **CSRF**：JWT Bearer 模式下不依赖 Cookie，无 CSRF 风险

## 已知技术债

- SQLite 单写者限制，并发超过 50 用户时需迁移 PostgreSQL
- 前端无自动化测试覆盖
- 合同 expired 状态自动流转未实现定时任务（MVP 手动触发）
- 附件存储使用本地文件系统，无冗余备份

## 关联 ADR 与最近变更

- ADR：待创建（docs/decisions/）
- 最近变更：见 git log iteration/0.0.1
- 技术方案：evidence/claude/technical-plan-0.0.1.json
- 任务拆解：evidence/claude/tasks-defined-0.0.1.json
