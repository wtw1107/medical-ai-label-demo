# Medical AI Label Demo

## 1. 项目简介

本项目是一个基于 **Label Studio** 的本地医学影像 AI 辅助标注 Demo，用于验证以下闭环：

```text
上传医学图像
→ 创建标注任务
→ 调用检测 / 分割模型生成 AI 预标注
→ 跳转 Label Studio 进行人工审核与修正
→ 保存人工确认后的 annotation
→ 导出 JSON / Mask PNG 等训练可用格式
```

当前项目已经完成的稳定能力包括：

- Label Studio 前端内嵌与图像级入口
- Label Studio 状态同步
- AI 预标注只读预览与导出面板增强
- 任务列表与任务导航
- 模型接入契约整理

当前阶段暂不包含：

- 登录 / 权限 / 多人协作
- DICOM / 3D / 视频标注
- 训练调度平台
- Label Studio 前端源码二次开发

## 2. 本地运行

标准本地端口：

- frontend: `5173`
- backend: `8000`
- Label Studio: `8080`
- model service: `9000`

一键启动：

```powershell
.\scripts\start-local-stack.ps1
```

强制重启：

```powershell
.\scripts\start-local-stack.ps1 -ForceRestart
```

停止本地栈：

```powershell
.\scripts\stop-local-stack.ps1
```

标准访问地址：

- frontend: `http://127.0.0.1:5173`
- backend docs: `http://127.0.0.1:8000/docs`
- model service docs: `http://127.0.0.1:9000/docs`
- Label Studio: `http://127.0.0.1:8080`

## 3. Frontend MVP

当前前端主要负责工作流编排，而不是替代 Label Studio 标注工作台：

- 数据集上传与任务创建
- 任务列表与任务详情
- AI 预标注触发
- 内嵌 Label Studio 工作台
- 图像级进入标注
- 状态同步
- AI 只读预览
- 导出与下载

说明：

- 首次使用前请先登录本地 Label Studio
- 如果 iframe 被浏览器或 Label Studio 策略拦截，请使用“在新窗口打开 Label Studio”
- 导出前建议先同步 Label Studio 状态

## 4. 模型接入契约

当前默认模型仍然是：

- `mock_detection`
- `mock_segmentation`

后端统一提供：

- `GET /api/models`
- `POST /api/tasks/{task_id}/prelabel`

其中预标注接口支持可选字段：

```json
{
  "detection_model_id": "mock_detection",
  "segmentation_model_id": "mock_segmentation"
}
```

如果选择未配置模型，后端会返回清晰错误，而不是直接崩溃。

## 5. DINO 检测模型资源说明

当前仓库已经补充了 **TN5000 UQ-DINO variance** 检测模型的轻量资源包，用于后续真实检测模型接入准备。

### 5.1 已纳入 Git 的轻量文件

```text
model_service/services/dino_detection_service.py
models/configs/dino_detection/dino_config.py
models/configs/dino_detection/label_map.json
models/configs/dino_detection/dino_requirements_freeze.txt
samples/dino_detection/sample_001_prediction.json
samples/dino_detection/sample_001.png
```

说明：

- `sample_001.png` 为本地 Demo 使用的脱敏样例图像
- `sample_001_prediction.json` 为样例预测输出
- `dino_detection_service.py` 为 DINO 检测服务封装
- `label_map.json` 中类别映射为：
  - `0 = benign thyroid nodule`
  - `1 = malignant thyroid nodule`

### 5.2 不纳入 Git 的文件

以下真实模型权重只允许保留在本地，不提交到 Git：

```text
models/weights/dino_detection/best.pth
```

`.gitignore` 已确保忽略：

- `models/weights/`
- `*.pth`
- `*.pt`
- `*.onnx`
- `*.ckpt`
- `*.safetensors`

### 5.3 资源用途

这批 DINO 资源当前只用于：

- 本地 inference demo 准备
- 模型服务接口对接准备
- 预测输出格式说明

当前 **不包含**：

- 真实分割模型接入
- 模型训练
- 模型下载逻辑
- 权重提交

## 6. DINO 预测输出参考

后续真实检测模型接入时，建议输出结构保持为：

```json
{
  "model_id": "real_detection_v1",
  "model_version": "uq-dino-variance-20260515",
  "model_type": "detection",
  "predictions": [
    {
      "label": "malignant thyroid nodule",
      "score": 0.91,
      "bbox": {
        "x": 102,
        "y": 88,
        "width": 122,
        "height": 133
      },
      "meta": {
        "label_id": 1,
        "box_unc": 0.03
      }
    }
  ]
}
```

这样可以继续兼容：

- Label Studio rectanglelabels prediction 转换
- 状态同步
- AI 只读预览
- simple_json / label_studio_json / mask_png 导出
## 7. Roboflow thyroid detection demo

The demo can optionally use the Roboflow Universe model
`thyroid-nodules-detection-test/3` as a real thyroid nodule detection backend.

- Set `ROBOFLOW_API_KEY` before running the validation script.
- Keep the API key only in local environment variables or `.env`, never in Git.
- The model is called through the Roboflow API and does not require local training.
- This model is only used for demo validation and is not a clinical diagnostic model.
- In the current integration stage, `real_detection_v1` is exposed through `/api/models` and can be selected for bbox / bbox_polygon prelabel.
- `real_segmentation_v1` remains `not_configured`; bbox_polygon still pairs real detection with `mock_segmentation`.
- If Roboflow returns `0 detections`, the request is treated as a valid model response rather than a system failure.
