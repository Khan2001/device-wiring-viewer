# 机房设备二维可视化编辑器

基于 Vue、FastAPI 和 PostgreSQL 的机房设备二维可视化编辑器。

当前完成：Iteration 0 工程初始化、Iteration 1 基础数据 API、Iteration 2 基础管理界面、Iteration 3 SVG 画布基础能力、Iteration 4 机房平面图、Iteration 5 机柜设备布局、Iteration 6 设备接口面板、Iteration 7 端口连线、Iteration 8 保存搜索导出。

## 快速启动

### 1. 准备环境

- Docker Desktop 或 Docker Engine
- Docker Compose v2

### 2. 配置环境变量

```bash
cp .env.example .env
```

生产环境请修改 `.env` 中的数据库密码。

### 3. 启动服务

```bash
docker compose up -d --build
```

打开：

```text
http://localhost:8080
```

### 4. 查看服务状态

```bash
docker compose ps
curl http://localhost:8080/api/health
curl http://localhost:8080/api/health/db
```

### 5. 停止服务

```bash
docker compose down
```

默认只停止容器，不删除 PostgreSQL 数据卷。删除数据需要明确执行：

```bash
docker compose down -v
```

## 数据备份

服务运行后可执行：

```bash
./scripts/backup.sh
```

脚本会在 `backups/` 下生成 PostgreSQL SQL 备份和设备图片压缩包。生产环境应将生成的目录复制到独立存储。

## 本地开发

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认运行在 `http://localhost:5173`，`/api` 请求会代理到 `http://localhost:8000`。

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

运行测试：

```bash
pytest
```

## 服务说明

| 服务 | 地址 | 作用 |
|---|---|---|
| frontend | `http://localhost:8080` | 浏览器页面和反向代理 |
| backend | Docker 内部 `http://backend:8000` | FastAPI API |
| db | Docker 内部 `db:5432` | PostgreSQL 数据库 |

当前页面提供项目、机房、机柜、设备和接口的基础维护，支持机房二维画布、网格背景、机柜拖动、网格吸附、缩放、平移、自动适配和布局保存；在设备面板中可以从实际接口坐标查看端口到端口的连接关系，拖拽端口创建连接，并维护连接属性。支持接口批量生成、全局搜索、JSON 导入/导出以及当前视图 SVG/PNG 导出。
