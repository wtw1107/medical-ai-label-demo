# Medical AI Label Demo

## 1. 项目简介

本项目是一个基于 **Label Studio** 的轻量级医学影像 AI 辅助标注 Demo，用于验证医学私有数据集的 AI 预标注、人工修正和结果导出流程。

项目目标不是重新开发一个完整标注平台，也不是让 AI 完全替代人工标注，而是实现一个最小可运行闭环：

```text
上传医学图像
→ 创建标注任务
→ 调用检测 / 分割模型生成 AI 预标注
→ 跳转 Label Studio 进行人工审核与修正
→ 保存人工确认后的 annotation
→ 导出 JSON / COCO / YOLO / Mask PNG 等训练可用格式
```

当前 Demo 优先支持：

- 医学图像上传；
- 检测框 bbox 预标注；
- 分割轮廓 polygon / mask 预标注；
- Label Studio 中人工修改和确认；
- 标注结果导出；
- 本地单机运行。

当前阶段暂不包含：

- 登录系统；
- 多用户权限；
- 复杂任务分配；
- DICOM / 3D / 视频标注；
- 训练调度平台；
- Label Studio 前端源码二次开发。

---

## 2. 如何运行

### 2.1 环境要求

建议本地安装：

```text
Python 3.10+
Node.js 18+
Docker
Docker Compose
```

如果只是先跑通 Label Studio 和后端流程，前端可以后续再启动。

---

### 2.2 项目目录结构

推荐项目结构如下：

```text
medical-ai-label-demo/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── frontend/                 # React 前端
│   └── src/
│
├── backend/                  # FastAPI 后端
│   └── app/
│
├── model_service/            # 模型服务，可先使用 Mock 模型
│   └── main.py
│
├── configs/
│   ├── models.yaml
│   └── label_configs/
│       ├── bbox.xml
│       ├── polygon.xml
│       └── bbox_polygon.xml
│
├── data/
│   ├── datasets/             # 上传数据
│   ├── exports/              # 导出结果
│   └── demo.db               # 本地 SQLite 数据库
│
└── scripts/
```

---

### 2.3 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

`.env` 示例：

```env
APP_ENV=local

BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

DATABASE_URL=sqlite:///./data/demo.db
DATA_ROOT=./data
MEDIA_BASE_URL=http://localhost:8000/media

LABEL_STUDIO_URL=http://localhost:8080
LABEL_STUDIO_API_TOKEN=your_label_studio_token_here

MODEL_SERVICE_URL=http://localhost:9000
DEFAULT_USER_ID=local_demo_user
```

注意：

- `LABEL_STUDIO_API_TOKEN` 需要在 Label Studio 中获取；
- 本地开发阶段可以先手动填写；
- 如果暂时没有真实模型，可以先使用 mock model service。

---

### 2.4 启动 Label Studio

推荐使用 Docker 启动 Label Studio：

```bash
docker run -it -p 8080:8080 \
  -v $(pwd)/data/label-studio:/label-studio/data \
  heartexlabs/label-studio:latest
```

启动后访问：

```text
http://localhost:8080
```

首次进入后创建账号，并在 Account / API Token 中获取 Token，填入 `.env` 的：

```env
LABEL_STUDIO_API_TOKEN=your_label_studio_token_here
```

---

### 2.5 启动后端服务

进入后端目录：

```bash
cd backend
```

创建虚拟环境：

```bash
python -m venv .venv
```

激活虚拟环境。

Windows：

```bash
.venv\Scripts\activate
```

macOS / Linux：

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动 FastAPI：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端接口文档地址：

```text
http://localhost:8000/docs
```

---

### 2.6 启动模型服务

进入模型服务目录：

```bash
cd model_service
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动模型服务：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 9000
```

本地 Demo 第一阶段可以先使用 Mock 模型：

- `/predict/detection` 返回固定 bbox；
- `/predict/segmentation` 返回固定 polygon；
- 确认流程能跑通后，再替换为真实 YOLO / DINO / SAM / MedSAM 模型。

健康检查：

```text
http://localhost:9000/health
```

---

### 2.7 启动前端页面

进入前端目录：

```bash
cd frontend
```

安装依赖：

```bash
npm install
```

启动前端：

```bash
npm run dev
```

默认访问：

```text
http://localhost:5173
```

---

### 2.8 本地 Demo 验证流程

完整验证步骤：

```text
1. 打开前端页面；
2. 上传 5–20 张医学图像；
3. 创建检测框 / 分割 / 检测框+分割任务；
4. 后端自动创建 Label Studio 项目；
5. 调用模型服务生成 AI 预标注；
6. 打开 Label Studio 工作台；
7. 查看 AI prediction；
8. 手动修改 bbox 或 polygon；
9. 保存 annotation；
10. 返回导出页面；
11. 选择 JSON / Mask PNG / COCO / YOLO 格式导出；
12. 下载导出 zip 文件。
```

---

## 3. 技术栈

### 3.1 前端

```text
React
TypeScript
Vite
Ant Design
Axios
React Router
```

前端负责：

- 数据上传页面；
- 任务创建页面；
- 预标注结果展示；
- Label Studio 跳转；
- 导出结果页面。

前端不负责：

- 图像标注画布；
- 模型推理；
- 直接操作 Label Studio API；
- 标注格式转换。

---

### 3.2 后端

```text
FastAPI
Pydantic
SQLAlchemy
SQLite
httpx
OpenCV
Pillow
NumPy
```

后端负责：

- 接收上传文件；
- 解压 zip；
- 保存图像；
- 创建数据集和任务记录；
- 调用 Label Studio API；
- 调用模型服务；
- 写入 Label Studio predictions；
- 拉取 Label Studio annotations；
- 导出 JSON / COCO / YOLO / Mask PNG。

---

### 3.3 标注平台

```text
Label Studio
Label Studio API
Label Studio predictions
Label Studio annotations
```

Label Studio 负责：

- 显示医学图像；
- 显示 AI 预标注；
- 支持 bbox 修改；
- 支持 polygon / mask 修改；
- 保存人工确认后的 annotation。

当前阶段不修改 Label Studio 源码。

---

### 3.4 模型服务

```text
Python
FastAPI
PyTorch / ONNX Runtime 可选
OpenCV
NumPy
Pillow
```

模型服务负责：

- 检测模型推理；
- 分割模型推理；
- 输出 bbox / polygon / mask；
- 返回统一 prediction 数据结构。

第一阶段建议先使用 Mock 模型跑通流程，后续替换为真实模型。

---

### 3.5 数据库与存储

本地 Demo：

```text
SQLite
Local filesystem
```

后续团队版可扩展为：

```text
PostgreSQL
NAS / MinIO / Object Storage
```

当前通过 SQLAlchemy 和 storage service 封装数据库与文件路径，避免后续迁移时大规模改代码。

---

## 4. 当前开发原则

1. 先跑通流程，再接真实模型；
2. 先用 Mock prediction 验证 Label Studio 显示；
3. 不自研标注画布；
4. 不改 Label Studio 前端源码；
5. 不做登录和权限系统；
6. 不把路径、Token、模型接口写死在代码里；
7. 所有配置放在 `.env` 或 `configs/` 中；
8. Label Studio API 统一由后端封装；
9. 模型调用统一由 model service 封装；
10. 导出格式转换统一放在 converters / scripts 中。
---

## 5. Frontend MVP

Frontend MVP lives in `frontend/` and focuses on AI-assisted labeling workflow orchestration instead of replacing the Label Studio workspace.

Start the frontend locally:

```bash
cd frontend
npm install
npm run dev
```

Default local URL:

```text
http://localhost:5173
```

Optional frontend env:

```env
VITE_API_BASE_URL=http://localhost:8000
```

The frontend MVP currently covers:

- dataset upload and task creation
- task detail and image status overview
- AI prelabel trigger and job status display
- embedded Label Studio workbench for in-page review
- image-level "进入标注" entry from the task image table
- fallback open-in-new-window entry for Label Studio
- export creation and zip download

Workbench notes:

- first-time users should log in to the local Label Studio instance before using the embedded workbench
- if the iframe is blocked by local browser or Label Studio security settings, use `在新窗口打开 Label Studio`
- after AI prelabel finishes, confirm or revise annotations in Label Studio and then return to the frontend to refresh status and export

Status sync notes:

- after saving annotations in Label Studio, return to the frontend and click `同步 Label Studio 状态`
- the frontend will pull the latest prediction and annotation status from Label Studio and update the task image table
- if the embedded iframe shows the login page, log in to local Label Studio first and then return to the frontend to continue syncing and reviewing

AI prediction read-only preview:

- after AI prelabel finishes and status has been synchronized, you can click `预览 AI 结果` in the image table
- the frontend renders a read-only bbox / polygon overlay for quick inspection only
- editing and human confirmation still happen inside the Label Studio workbench

Export panel:

- the export panel supports `simple_json`, `label_studio_json`, and `mask_png`
- it is recommended to sync Label Studio status before export so the latest saved human annotations are reflected in the export summary
- the task list page at `/tasks` lets you reopen existing annotation tasks and continue the workflow without going back through the upload page

## 6. Standard Local Startup

Use the standard local ports below for day-to-day development:

- frontend: `5173`
- backend: `8000`
- Label Studio: `8080`
- model service: `9000`

One-click startup on Windows PowerShell:

```powershell
.\scripts\start-local-stack.ps1
```

If you want to force-restart the standard ports:

```powershell
.\scripts\start-local-stack.ps1 -ForceRestart
```

Stop the standard local stack:

```powershell
.\scripts\stop-local-stack.ps1
```

Standard local URLs:

- frontend: `http://127.0.0.1:5173/index.html`
- backend docs: `http://127.0.0.1:8000/docs`
- model service docs: `http://127.0.0.1:9000/docs`
- Label Studio: `http://127.0.0.1:8080`

## 7. Model Integration Contract

The current project still uses `mock_detection` and `mock_segmentation` by default.

This phase prepares the system for future real-model integration without changing the verified upload, prelabel, sync, preview, and export flow:

- backend model registry: `GET /api/models`
- frontend model selection in the AI prelabel panel
- prelabel request supports optional `detection_model_id` and `segmentation_model_id`
- mock models remain available as the default fallback
- `real_detection_v1` and `real_segmentation_v1` are placeholder entries only

If a placeholder real model is selected before it is configured, the backend returns a clear error instead of crashing.

Current expectations for model outputs:

- detection models should provide `model_id`, `model_version`, `model_type`, `score`, and bbox results
- segmentation models should provide `model_id`, `model_version`, `model_type`, `score`, and polygon results

Recommended future detection output:

```json
{
  "model_id": "real_detection_v1",
  "model_version": "v1.0",
  "model_type": "detection",
  "predictions": [
    {
      "label": "lesion",
      "score": 0.87,
      "bbox": {
        "x": 120,
        "y": 80,
        "width": 160,
        "height": 130
      }
    }
  ]
}
```

Recommended future segmentation output:

```json
{
  "model_id": "real_segmentation_v1",
  "model_version": "v1.0",
  "model_type": "segmentation",
  "predictions": [
    {
      "label": "lesion",
      "score": 0.81,
      "polygon": [
        [31.2, 42.1],
        [35.4, 39.8],
        [41.7, 43.6]
      ]
    }
  ]
}
```
