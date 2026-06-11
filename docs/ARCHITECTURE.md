# 医学影像 AI 辅助标注 Demo 系统架构设计

## 1. 架构目标

本系统基于 Label Studio 做轻量实现，目标是完成一个本地可运行的医学影像 AI 辅助标注 Demo。

核心流程为：

```text
上传医学图像
→ 创建标注任务
→ 调用检测 / 分割模型生成 AI 预标注
→ 跳转 Label Studio 人工审核修正
→ 拉取人工确认后的标注结果
→ 导出 JSON / COCO / YOLO / Mask PNG
```

本架构设计遵循以下原则：

1. **简单优先**：当前只服务本地 Demo，不引入复杂权限、多人协作、任务分配和平台级调度。
2. **边界清晰**：上传、任务、Label Studio 集成、模型服务、导出转换分别封装，避免代码混在一起。
3. **可平滑扩展**：本地使用 SQLite 和本地文件夹，后续可替换为 PostgreSQL、NAS/MinIO、异步任务队列。
4. **不重写标注工作台**：Label Studio 负责 bbox、polygon、mask 的显示与人工修正。
5. **AI 结果只是预标注**：模型输出作为 prediction，人工保存后的 annotation 才作为正式结果导出。

------

# 2. 总体架构

## 2.1 系统组成

系统由 5 个部分组成：

```text
React 前端
FastAPI 后端
Label Studio 标注平台
Model Service 模型服务
本地数据存储
```

## 2.2 架构图

```text
┌──────────────────────────────────────┐
│              React 前端               │
│ 上传页 / 预标注结果页 / 导出页          │
└──────────────────┬───────────────────┘
                   │ HTTP API
                   ↓
┌──────────────────────────────────────┐
│              FastAPI 后端              │
│ 上传管理 / 任务管理 / LS API / 导出转换 │
└───────────┬───────────────┬──────────┘
            │               │
            │               │ 调用模型接口
            │               ↓
            │   ┌──────────────────────────┐
            │   │       Model Service        │
            │   │ 检测模型 / 分割模型 / Mock │
            │   └──────────────────────────┘
            │
            │ 调用 Label Studio API
            ↓
┌──────────────────────────────────────┐
│            Label Studio               │
│ prediction 展示 / annotation 保存      │
└──────────────────────────────────────┘

本地存储：
data/datasets/
data/exports/

本地数据库：
SQLite
```

## 2.3 模块职责

| 模块          | 职责                                                         |
| ------------- | ------------------------------------------------------------ |
| React 前端    | 提供上传、任务创建、预标注状态、导出结果等轻量页面           |
| FastAPI 后端  | 作为业务流程中心，管理数据集、任务、模型调用、Label Studio API、导出 |
| Label Studio  | 负责图像标注工作台、AI 预标注展示、人工修改和 annotation 保存 |
| Model Service | 负责调用检测模型、分割模型，输出 bbox / polygon / mask       |
| 本地存储      | 保存上传图像、预标注文件、导出结果和中间文件                 |
| SQLite        | 保存数据集、图像、任务、预标注任务和导出记录等元数据         |

------

# 3. 技术栈

## 3.1 前端

```text
React
TypeScript
Vite
Ant Design
Axios
React Router
```

### 前端职责

前端不负责复杂标注画布，只负责 Demo 外层流程：

1. 上传数据；
2. 创建任务；
3. 展示预标注结果；
4. 打开 Label Studio 工作台；
5. 发起导出；
6. 下载导出文件。

------

## 3.2 后端

```text
FastAPI
Pydantic
SQLAlchemy
SQLite
httpx
OpenCV
Pillow
NumPy
zipfile
```

### 后端职责

1. 接收图片或 zip 上传；
2. 解压和保存文件；
3. 记录数据集和图像信息；
4. 创建 Label Studio 项目；
5. 生成 Label Studio labeling config；
6. 导入 Label Studio tasks；
7. 调用模型服务生成 predictions；
8. 将 predictions 写入 Label Studio；
9. 拉取 Label Studio annotations；
10. 转换导出格式；
11. 打包导出文件。

------

## 3.3 标注平台

```text
Label Studio Docker
Label Studio API
Label Studio predictions
Label Studio annotations
```

### 使用方式

当前阶段不修改 Label Studio 源码。

只使用：

1. Label Studio API；
2. 标注配置 labeling config；
3. prediction 预标注；
4. annotation 人工确认结果；
5. 原始 JSON 导出能力。

------

## 3.4 模型服务

```text
Python
FastAPI
PyTorch / ONNX Runtime 可选
OpenCV
NumPy
Pillow
```

第一版可以先支持 Mock 模型输出，确保流程跑通。

后续再替换为真实模型：

1. YOLO / DINO / UQ-DINO：输出 bbox；
2. SAM / MedSAM / U-Net / nnU-Net：输出 mask 或 polygon。

------

## 3.5 数据库

当前本地 Demo：

```text
SQLite
```

后续团队版可替换为：

```text
PostgreSQL
```

为降低迁移成本，后端统一使用 SQLAlchemy ORM，不直接写死 SQLite 特性。

------

# 4. 项目目录结构

推荐目录如下：

```text
medical-ai-label-demo/
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   ├── client.ts
│       │   ├── datasets.ts
│       │   ├── tasks.ts
│       │   └── exports.ts
│       ├── pages/
│       │   ├── UploadTaskPage.tsx
│       │   ├── PrelabelResultPage.tsx
│       │   └── ExportPage.tsx
│       ├── components/
│       │   ├── DatasetUpload.tsx
│       │   ├── TaskTypeSelector.tsx
│       │   ├── ModelSelector.tsx
│       │   ├── ImageStatusTable.tsx
│       │   └── ExportFormatSelector.tsx
│       ├── types/
│       │   └── api.ts
│       └── utils/
│           └── format.ts
│
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config.py
│       │   └── constants.py
│       ├── db/
│       │   ├── session.py
│       │   ├── base.py
│       │   └── models.py
│       ├── schemas/
│       │   ├── dataset.py
│       │   ├── task.py
│       │   ├── prelabel.py
│       │   └── export.py
│       ├── routers/
│       │   ├── datasets.py
│       │   ├── tasks.py
│       │   ├── prelabel.py
│       │   └── exports.py
│       ├── services/
│       │   ├── storage_service.py
│       │   ├── label_studio_service.py
│       │   ├── model_service.py
│       │   ├── prelabel_service.py
│       │   └── export_service.py
│       ├── converters/
│       │   ├── label_studio_parser.py
│       │   ├── coco_converter.py
│       │   ├── yolo_converter.py
│       │   └── mask_converter.py
│       └── utils/
│           ├── image_utils.py
│           ├── file_utils.py
│           └── id_utils.py
│
├── model_service/
│   ├── requirements.txt
│   ├── main.py
│   ├── schemas.py
│   ├── services/
│   │   ├── detection_service.py
│   │   └── segmentation_service.py
│   ├── models/
│   │   └── README.md
│   └── utils/
│       ├── image_loader.py
│       └── geometry.py
│
├── configs/
│   ├── models.yaml
│   └── label_configs/
│       ├── bbox.xml
│       ├── polygon.xml
│       └── bbox_polygon.xml
│
├── data/
│   ├── datasets/
│   ├── exports/
│   └── demo.db
│
└── scripts/
    ├── init_label_studio.py
    ├── convert_ls_to_coco.py
    ├── convert_ls_to_yolo.py
    └── convert_polygon_to_mask.py
```

------

# 5. 核心模块划分

## 5.1 frontend 前端模块

### 页面模块

| 页面                 | 说明                         |
| -------------------- | ---------------------------- |
| `UploadTaskPage`     | 上传图片 / zip，创建标注任务 |
| `PrelabelResultPage` | 展示 AI 预标注进度和结果     |
| `ExportPage`         | 展示确认统计，选择格式并导出 |

### 组件模块

| 组件                   | 说明                         |
| ---------------------- | ---------------------------- |
| `DatasetUpload`        | 上传图片或压缩包             |
| `TaskTypeSelector`     | 选择检测框、分割、检测+分割  |
| `ModelSelector`        | 选择检测模型、分割模型       |
| `ImageStatusTable`     | 展示图像预标注和人工确认状态 |
| `ExportFormatSelector` | 选择导出格式和范围           |

### 前端不做的事情

1. 不做标注画布；
2. 不直接处理 mask；
3. 不直接调用模型；
4. 不直接调用 Label Studio API；
5. 不保存业务状态。

所有业务操作都通过 FastAPI 后端完成。

------

## 5.2 backend 后端模块

后端是系统核心，负责流程控制。

### `storage_service.py`

负责文件存储。

功能：

1. 保存上传文件；
2. 解压 zip；
3. 生成数据集目录；
4. 过滤非图片文件；
5. 返回图像路径和访问 URL；
6. 生成导出目录。

------

### `label_studio_service.py`

负责和 Label Studio 通信。

功能：

1. 创建 Label Studio 项目；
2. 设置 labeling config；
3. 导入 tasks；
4. 写入 predictions；
5. 获取 project URL；
6. 拉取 annotations；
7. 获取任务完成情况。

后端其他模块不直接调用 Label Studio API，统一通过这个 service 封装。

------

### `model_service.py`

负责调用模型服务。

功能：

1. 根据模型配置读取 endpoint；
2. 调用检测模型；
3. 调用分割模型；
4. 获取 bbox / polygon / mask；
5. 处理模型不可用异常；
6. 返回统一预测结果。

注意：这里不直接写 YOLO 或 SAM 代码，只调用模型服务接口。

------

### `prelabel_service.py`

负责预标注流程。

功能：

1. 根据任务类型选择模型；
2. 遍历图像；
3. 调用 `model_service`；
4. 将模型结果转换为 Label Studio prediction；
5. 调用 `label_studio_service` 写入 prediction；
6. 更新图像状态和任务状态。

第一版可以同步处理少量图片；但接口设计上仍保留 `job_id` 和状态字段，后续可替换成异步队列。

------

### `export_service.py`

负责导出结果。

功能：

1. 从 Label Studio 拉取 annotations；
2. 过滤已确认结果；
3. 转换为内部统一格式；
4. 导出 Label Studio JSON；
5. 导出简化 JSON；
6. 导出 COCO JSON；
7. 导出 YOLO TXT；
8. polygon 转 Mask PNG；
9. 打包 zip。

------

### `converters/`

负责格式转换，不掺杂业务流程。

| 文件                     | 说明                         |
| ------------------------ | ---------------------------- |
| `label_studio_parser.py` | 解析 Label Studio annotation |
| `coco_converter.py`      | 转 COCO                      |
| `yolo_converter.py`      | 转 YOLO                      |
| `mask_converter.py`      | polygon 转 mask PNG          |

------

## 5.3 model_service 模型服务模块

模型服务独立运行，避免和业务后端混在一起。

### 接口

```text
POST /predict/detection
POST /predict/segmentation
GET /health
```

### 第一版策略

第一版可以先实现 Mock：

1. 检测接口返回固定 bbox；
2. 分割接口返回固定 polygon；
3. 流程确认无误后，再接真实模型。

### 后续扩展

后续可以替换为：

1. YOLO 检测；
2. DINO / UQ-DINO 检测；
3. SAM / MedSAM 分割；
4. 自定义分割模型。

------

# 6. 数据模型设计

当前只设计最小必要数据模型。

## 6.1 Dataset 数据集表

表名：`datasets`

用途：记录一次上传形成的数据集。

| 字段        | 类型     | 说明                     |
| ----------- | -------- | ------------------------ |
| id          | String   | 数据集 ID                |
| name        | String   | 数据集名称               |
| description | Text     | 说明，可为空             |
| data_type   | String   | 当前默认 image           |
| image_count | Integer  | 图像数量                 |
| root_dir    | String   | 本地存储目录             |
| status      | String   | uploaded / ready / error |
| created_by  | String   | 本地默认 local_demo_user |
| created_at  | DateTime | 创建时间                 |
| updated_at  | DateTime | 更新时间                 |

------

## 6.2 ImageItem 图像表

表名：`image_items`

用途：记录每张上传图像。

| 字段          | 类型     | 说明                                                         |
| ------------- | -------- | ------------------------------------------------------------ |
| id            | String   | 图像 ID                                                      |
| dataset_id    | String   | 所属数据集                                                   |
| filename      | String   | 文件名                                                       |
| file_path     | String   | 本地路径                                                     |
| file_url      | String   | 给 Label Studio 或前端访问的 URL                             |
| width         | Integer  | 图像宽度                                                     |
| height        | Integer  | 图像高度                                                     |
| status        | String   | uploaded / prelabeling / prelabel_done / prelabel_failed / confirmed |
| error_message | Text     | 错误信息                                                     |
| created_at    | DateTime | 创建时间                                                     |
| updated_at    | DateTime | 更新时间                                                     |

------

## 6.3 AnnotationTask 标注任务表

表名：`annotation_tasks`

用途：记录一次标注任务及其 Label Studio 项目映射。

| 字段                     | 类型     | 说明                                                   |
| ------------------------ | -------- | ------------------------------------------------------ |
| id                       | String   | 任务 ID                                                |
| dataset_id               | String   | 所属数据集                                             |
| name                     | String   | 任务名称                                               |
| task_type                | String   | bbox / polygon / bbox_polygon                          |
| label_name               | String   | 标签名称，如病灶                                       |
| det_model_id             | String   | 检测模型 ID，可为空                                    |
| seg_model_id             | String   | 分割模型 ID，可为空                                    |
| label_studio_project_id  | Integer  | Label Studio 项目 ID                                   |
| label_studio_project_url | String   | Label Studio 项目地址                                  |
| require_human_confirm    | Boolean  | 是否需要人工确认，默认 true                            |
| status                   | String   | created / prelabeling / reviewing / exportable / error |
| created_by               | String   | 当前默认 local_demo_user                               |
| created_at               | DateTime | 创建时间                                               |
| updated_at               | DateTime | 更新时间                                               |

------

## 6.4 PrelabelJob 预标注任务表

表名：`prelabel_jobs`

用途：记录一次 AI 预标注执行。

| 字段          | 类型     | 说明                                   |
| ------------- | -------- | -------------------------------------- |
| id            | String   | Job ID                                 |
| task_id       | String   | 标注任务 ID                            |
| status        | String   | pending / running / completed / failed |
| total_count   | Integer  | 总图像数量                             |
| success_count | Integer  | 成功数量                               |
| failed_count  | Integer  | 失败数量                               |
| started_at    | DateTime | 开始时间                               |
| finished_at   | DateTime | 完成时间                               |
| error_message | Text     | 总体错误信息                           |
| created_at    | DateTime | 创建时间                               |

------

## 6.5 ModelConfig 模型配置表

表名：`model_configs`

用途：记录可用模型。

第一版也可以不落库，直接用 `configs/models.yaml`。
如果想保持扩展性，建议仍建表或从配置文件读取后展示。

| 字段        | 类型     | 说明                     |
| ----------- | -------- | ------------------------ |
| id          | String   | 模型 ID                  |
| name        | String   | 模型名称                 |
| task_type   | String   | detection / segmentation |
| version     | String   | 模型版本                 |
| endpoint    | String   | 模型服务接口             |
| status      | String   | available / unavailable  |
| description | Text     | 模型说明                 |
| created_at  | DateTime | 创建时间                 |

------

## 6.6 ExportRecord 导出记录表

表名：`export_records`

用途：记录导出任务和文件。

| 字段          | 类型     | 说明                                           |
| ------------- | -------- | ---------------------------------------------- |
| id            | String   | 导出 ID                                        |
| task_id       | String   | 标注任务 ID                                    |
| export_format | String   | ls_json / simple_json / coco / yolo / mask_png |
| export_range  | String   | confirmed_only / all                           |
| file_path     | String   | 导出 zip 路径                                  |
| status        | String   | running / completed / failed                   |
| image_count   | Integer  | 导出图像数量                                   |
| error_message | Text     | 错误信息                                       |
| created_by    | String   | 本地默认 local_demo_user                       |
| created_at    | DateTime | 创建时间                                       |
| finished_at   | DateTime | 完成时间                                       |

------

# 7. 状态设计

## 7.1 图像状态

```text
uploaded
→ prelabeling
→ prelabel_done
→ confirmed
→ exportable
```

异常状态：

```text
prelabel_failed
manual_required
ignored
```

说明：

| 状态            | 含义                      |
| --------------- | ------------------------- |
| uploaded        | 已上传，未预标注          |
| prelabeling     | 正在生成 AI 预标注        |
| prelabel_done   | AI 预标注完成，待人工确认 |
| prelabel_failed | 预标注失败                |
| confirmed       | 已保存人工 annotation     |
| exportable      | 可导出                    |
| manual_required | 需要人工重标              |
| ignored         | 无法判断或不参与导出      |

------

## 7.2 任务状态

```text
created
→ prelabeling
→ reviewing
→ exportable
→ exported
```

异常状态：

```text
error
```

说明：

| 状态        | 含义           |
| ----------- | -------------- |
| created     | 任务已创建     |
| prelabeling | 正在预标注     |
| reviewing   | 待人工审核修正 |
| exportable  | 存在可导出结果 |
| exported    | 已导出         |
| error       | 任务异常       |

------

## 7.3 预标注任务状态

```text
pending
→ running
→ completed
```

异常：

```text
failed
partial_failed
```

------

# 8. 核心数据流

## 8.1 上传数据流

```text
前端上传图片 / zip
→ FastAPI 接收文件
→ storage_service 保存原始文件
→ 如果是 zip，解压图片
→ 读取图像尺寸
→ 创建 dataset 记录
→ 创建 image_item 记录
→ 返回 dataset_id 和图像列表
```

------

## 8.2 创建任务流

```text
前端提交任务配置
→ FastAPI 创建 annotation_task
→ 根据 task_type 选择 labeling config
→ label_studio_service 创建 Label Studio 项目
→ label_studio_service 导入图片 tasks
→ 保存 label_studio_project_id
→ 返回 task_id
```

------

## 8.3 AI 预标注流

```text
前端点击生成预标注
→ FastAPI 创建 prelabel_job
→ prelabel_service 遍历 image_items
→ model_service 调用检测 / 分割模型
→ 转换为 Label Studio prediction 格式
→ label_studio_service 写入 prediction
→ 更新 image_item 状态
→ 更新 prelabel_job 统计
```

第一版可以同步执行。
后续如果数据量变大，可将 `prelabel_service` 替换为后台 worker。

------

## 8.4 人工修正流

```text
用户点击进入 Label Studio
→ 查看 AI prediction
→ 修改 bbox / polygon
→ 选择审核状态
→ 保存 annotation
→ Label Studio 保存正式标注
```

系统规则：

```text
prediction = AI 预标注
annotation = 人工确认后的正式标注
```

未保存 annotation 的结果不进入正式导出。

------

## 8.5 导出流

```text
前端选择导出格式
→ FastAPI 调用 label_studio_service 拉取 annotations
→ label_studio_parser 转内部统一格式
→ export_service 根据格式调用 converter
→ 生成结果文件
→ 打包 zip
→ 创建 export_record
→ 返回下载地址
```

------

# 9. Label Studio 集成设计

## 9.1 Labeling Config

系统根据任务类型自动选择配置。

### bbox 任务

使用：

```text
RectangleLabels
Choices
TextArea
```

### polygon 任务

使用：

```text
PolygonLabels
Choices
TextArea
```

### bbox + polygon 任务

同时使用：

```text
RectangleLabels
PolygonLabels
Choices
TextArea
```

------

## 9.2 Label Studio Task 格式

每张图像生成一个 task。

```json
{
  "data": {
    "image": "http://localhost:8000/media/datasets/ds_001/images/img_001.png"
  },
  "meta": {
    "image_id": "img_001",
    "dataset_id": "ds_001"
  }
}
```

------

## 9.3 Prediction 格式

### bbox prediction

```json
{
  "from_name": "bbox",
  "to_name": "image",
  "type": "rectanglelabels",
  "value": {
    "x": 18.5,
    "y": 22.3,
    "width": 34.2,
    "height": 28.1,
    "rectanglelabels": ["病灶"]
  },
  "score": 0.91
}
```

### polygon prediction

```json
{
  "from_name": "lesion_polygon",
  "to_name": "image",
  "type": "polygonlabels",
  "value": {
    "points": [[32.1, 40.2], [36.5, 38.4], [42.8, 41.0]],
    "polygonlabels": ["病灶轮廓"]
  },
  "score": 0.86
}
```

------

# 10. 模型服务接口设计

## 10.1 健康检查

```http
GET /health
```

返回：

```json
{
  "status": "ok"
}
```

------

## 10.2 检测模型接口

```http
POST /predict/detection
```

请求：

```json
{
  "image_url": "http://backend:8000/media/datasets/ds_001/images/img_001.png",
  "image_id": "img_001",
  "model_id": "thyroid_yolo_v1"
}
```

返回：

```json
{
  "model_id": "thyroid_yolo_v1",
  "model_version": "v1.0",
  "results": [
    {
      "label": "病灶",
      "bbox": [120, 80, 164, 148],
      "score": 0.91
    }
  ]
}
```

------

## 10.3 分割模型接口

```http
POST /predict/segmentation
```

请求：

```json
{
  "image_url": "http://backend:8000/media/datasets/ds_001/images/img_001.png",
  "image_id": "img_001",
  "model_id": "medsam_v1",
  "prompts": {
    "bbox": [120, 80, 164, 148]
  }
}
```

返回：

```json
{
  "model_id": "medsam_v1",
  "model_version": "v1.0",
  "results": [
    {
      "label": "病灶轮廓",
      "polygon": [[120, 80], [135, 76], [160, 92]],
      "score": 0.86
    }
  ]
}
```

------

# 11. API 设计

## 11.1 上传数据集

```http
POST /api/datasets/upload
```

返回：

```json
{
  "dataset_id": "ds_001",
  "name": "甲状腺超声测试数据",
  "image_count": 20,
  "images": [
    {
      "id": "img_001",
      "filename": "thyroid_001.png",
      "status": "uploaded"
    }
  ]
}
```

------

## 11.2 创建标注任务

```http
POST /api/tasks
```

请求：

```json
{
  "dataset_id": "ds_001",
  "name": "甲状腺结节 AI 辅助标注任务",
  "task_type": "bbox_polygon",
  "label_name": "病灶",
  "det_model_id": "thyroid_yolo_v1",
  "seg_model_id": "medsam_v1",
  "require_human_confirm": true
}
```

返回：

```json
{
  "task_id": "task_001",
  "label_studio_project_id": 12,
  "status": "created"
}
```

------

## 11.3 启动预标注

```http
POST /api/tasks/{task_id}/prelabel
```

返回：

```json
{
  "job_id": "job_001",
  "task_id": "task_001",
  "status": "running"
}
```

------

## 11.4 查询预标注状态

```http
GET /api/prelabel-jobs/{job_id}
```

返回：

```json
{
  "job_id": "job_001",
  "status": "completed",
  "total_count": 20,
  "success_count": 18,
  "failed_count": 2
}
```

------

## 11.5 获取 Label Studio 链接

```http
GET /api/tasks/{task_id}/label-studio-url
```

返回：

```json
{
  "url": "http://localhost:8080/projects/12/data"
}
```

------

## 11.6 获取任务图像状态

```http
GET /api/tasks/{task_id}/images
```

返回：

```json
{
  "task_id": "task_001",
  "images": [
    {
      "image_id": "img_001",
      "filename": "thyroid_001.png",
      "status": "prelabel_done",
      "has_prediction": true,
      "has_annotation": false
    }
  ]
}
```

------

## 11.7 发起导出

```http
POST /api/tasks/{task_id}/exports
```

请求：

```json
{
  "format": "mask_png",
  "range": "confirmed_only"
}
```

返回：

```json
{
  "export_id": "export_001",
  "status": "running"
}
```

------

## 11.8 下载导出文件

```http
GET /api/exports/{export_id}/download
```

返回文件：

```text
export_001.zip
```

------

# 12. 配置文件设计

## 12.1 `.env`

```env
APP_ENV=local
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

DATABASE_URL=sqlite:///./data/demo.db

DATA_ROOT=./data
MEDIA_BASE_URL=http://localhost:8000/media

LABEL_STUDIO_URL=http://localhost:8080
LABEL_STUDIO_API_TOKEN=your_token_here

MODEL_SERVICE_URL=http://localhost:9000
DEFAULT_USER_ID=local_demo_user
```

------

## 12.2 `configs/models.yaml`

```yaml
models:
  - id: mock_detection
    name: Mock 病灶检测模型
    task_type: detection
    version: v0.1
    endpoint: http://localhost:9000/predict/detection
    status: available

  - id: mock_segmentation
    name: Mock 病灶分割模型
    task_type: segmentation
    version: v0.1
    endpoint: http://localhost:9000/predict/segmentation
    status: available

  - id: thyroid_yolo_v1
    name: 甲状腺结节检测模型
    task_type: detection
    version: v1.0
    endpoint: http://localhost:9000/predict/detection
    status: unavailable

  - id: medsam_v1
    name: MedSAM 分割模型
    task_type: segmentation
    version: v1.0
    endpoint: http://localhost:9000/predict/segmentation
    status: unavailable
```

------

# 13. 代码规范建议

## 13.1 总体规范

1. 业务逻辑不要写在 router 里；
2. router 只负责接收请求、调用 service、返回结果；
3. Label Studio API 只能通过 `label_studio_service.py` 调用；
4. 文件路径只能通过 `storage_service.py` 生成；
5. 模型调用只能通过 `model_service.py`；
6. 导出转换只能通过 `export_service.py` 和 `converters/`；
7. 不在前端写死后端地址，统一使用环境变量；
8. 不在代码里写死模型路径和 Label Studio token；
9. 所有 ID 由后端统一生成；
10. 所有状态使用常量或枚举，不直接散落字符串。

------

## 13.2 后端代码规范

### router 示例结构

```python
@router.post("/datasets/upload")
def upload_dataset(...):
    return dataset_service.upload_dataset(...)
```

router 中不要直接写：

1. 文件保存；
2. zip 解压；
3. 数据库复杂逻辑；
4. Label Studio API 调用；
5. 模型推理。

这些都放在 service 中。

------

### service 分层原则

| 层        | 负责内容       |
| --------- | -------------- |
| router    | API 输入输出   |
| schema    | 请求和响应格式 |
| service   | 业务逻辑       |
| db model  | 数据表结构     |
| converter | 格式转换       |
| utils     | 通用工具函数   |

------

### 命名规范

| 类型        | 规范                                          |
| ----------- | --------------------------------------------- |
| 文件名      | snake_case                                    |
| Python 函数 | snake_case                                    |
| Python 类   | PascalCase                                    |
| 数据库表名  | snake_case 复数                               |
| API 路径    | kebab-case 或 snake_case，建议统一 kebab-case |
| 前端组件    | PascalCase                                    |
| 前端函数    | camelCase                                     |

------

### 状态常量

建议在 `core/constants.py` 中定义：

```python
class ImageStatus:
    UPLOADED = "uploaded"
    PRELABELING = "prelabeling"
    PRELABEL_DONE = "prelabel_done"
    PRELABEL_FAILED = "prelabel_failed"
    CONFIRMED = "confirmed"
    IGNORED = "ignored"
```

不要在代码中到处手写 `"prelabel_done"`。

------

## 13.3 前端代码规范

1. 页面组件放在 `pages/`；
2. 可复用组件放在 `components/`；
3. API 请求放在 `api/`；
4. 类型定义放在 `types/`；
5. 页面不直接拼接后端 URL；
6. 表格字段与状态 Tag 封装成独立组件；
7. 上传、任务创建、导出不要写在一个巨大页面中；
8. 每个页面保持一个清晰主操作按钮。

------

## 13.4 数据库规范

1. 所有表都有 `id`；
2. 所有主要表都有 `created_at` 和 `updated_at`；
3. 本地版也保留 `created_by` 字段；
4. 外键字段统一使用 `{object}_id`；
5. 状态字段统一命名为 `status`；
6. 错误信息统一命名为 `error_message`；
7. 文件路径字段统一命名为 `file_path`；
8. URL 字段统一命名为 `file_url` 或 `download_url`。

------

# 14. 当前不做但预留的扩展点

## 14.1 用户登录

当前不做登录。

但数据表保留：

```text
created_by
updated_by
confirmed_by
```

本地默认值：

```text
local_demo_user
```

后续接登录时只需替换用户来源。

------

## 14.2 PostgreSQL

当前使用 SQLite。

但使用 SQLAlchemy，并通过 `.env` 配置 `DATABASE_URL`。
后续切 PostgreSQL 不改业务代码。

------

## 14.3 异步任务队列

当前可以同步处理小批量数据。

但 `prelabel_job` 和 `export_record` 已按 job 方式设计。
后续可将预标注和导出替换为 Celery / RQ / Redis worker。

------

## 14.4 存储扩展

当前使用本地目录。

但所有文件访问通过 `storage_service.py`。
后续可将本地文件替换为 NAS、MinIO 或对象存储。

------

## 14.5 模型扩展

当前可使用 Mock 模型。

但模型通过 `models.yaml` 和 `model_service.py` 调用。
后续新增 YOLO、DINO、SAM、MedSAM 不需要改任务主流程。

------

# 15. 当前不要增加的复杂度

第一版明确不做：

1. 多用户登录；
2. 权限系统；
3. 复杂审核流程；
4. 多人任务分配；
5. 训练任务调度；
6. 模型版本生命周期；
7. DICOM；
8. 视频；
9. 3D；
10. 主动学习看板；
11. Label Studio 前端源码二开；
12. Kubernetes；
13. 分布式任务队列；
14. 复杂缓存系统。

这些后续都可以扩展，但不进入当前架构。

------

# 16. 推荐开发顺序

## Step 1：基础环境

目标：

1. 启动 Label Studio；
2. 启动 FastAPI；
3. 启动 React；
4. 启动 Mock Model Service。

验收：

```text
四个服务都能本地访问。
```

------

## Step 2：上传数据

目标：

1. 前端上传图片 / zip；
2. 后端保存文件；
3. 创建 dataset 和 image_item；
4. 前端显示图片列表。

验收：

```text
上传 5 张图片后，前端表格显示 5 条 image_item。
```

------

## Step 3：创建 Label Studio 项目

目标：

1. 前端选择任务类型；
2. 后端创建 annotation_task；
3. 后端调用 Label Studio API 创建项目；
4. 后端导入图片 tasks；
5. 返回 Label Studio 项目链接。

验收：

```text
点击“进入标注工作台”后，可以在 Label Studio 看到上传图片。
```

------

## Step 4：Mock 预标注

目标：

1. Model Service 返回固定 bbox / polygon；
2. 后端转换为 Label Studio prediction；
3. 写入 Label Studio；
4. 工作台显示 AI 预标注。

验收：

```text
Label Studio 中打开图片时，可以看到预标注框或轮廓。
```

------

## Step 5：人工修正与保存

目标：

1. 用户在 Label Studio 修改 prediction；
2. 保存 annotation；
3. 后端能拉取 annotation；
4. 前端状态更新为已确认。

验收：

```text
修改一张图后，前端显示该图已确认。
```

------

## Step 6：导出结果

目标：

1. 导出 Label Studio JSON；
2. 导出简化 JSON；
3. polygon 转 mask PNG；
4. 打包 zip 下载。

验收：

```text
点击导出后，可以下载 zip，里面包含 json 和 mask 文件。
```

------

# 17. 最终架构总结

本系统采用“自研轻量外壳 + Label Studio 工作台 + 独立模型服务”的架构：

```text
React 负责流程页面；
FastAPI 负责业务编排；
Label Studio 负责标注工作台；
Model Service 负责 AI 预标注；
SQLite 和本地目录负责本地 Demo 数据存储。
```

该架构能满足当前需求：

1. 本地运行；
2. 无需登录；
3. 支持上传；
4. 支持 AI 预标注；
5. 支持人工修正；
6. 支持导出；
7. 代码结构清晰；
8. 后续可扩展到团队版。

同时，它避免了当前阶段不必要的复杂度：

1. 不自研标注画布；
2. 不引入复杂权限；
3. 不上分布式队列；
4. 不做完整平台化；
5. 不改 Label Studio 源码。

这是当前最适合该 Demo 的简单、清晰、可落地架构。