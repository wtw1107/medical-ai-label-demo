# 0611-医学 AI 辅助标注 Demo 阶段性任务汇报

## 一、当前阶段总体进展

目前已完成医学 AI 辅助标注 Demo 的后端主流程开发与阶段性验证。系统已从最初的项目脚手架，推进到“数据上传、标注任务创建、Label Studio 集成、Mock 模型服务、AI 预标注、标注结果导出”等核心功能模块。

当前 Demo 已基本跑通以下业务链路：

数据上传
→ 创建标注任务
→ 自动创建 Label Studio 项目
→ 导入图片任务
→ 在 Label Studio 中显示图像
→ 支持人工框选和轮廓标注
→ Mock 模型生成预标注结果
→ 后端写入 Label Studio prediction
→ 人工修正并保存 annotation
→ 导出标注结果

该阶段重点不是实现完整平台化系统，而是先验证医学影像 AI 辅助标注的最小闭环，为后续前端页面封装、真实模型接入和平台功能扩展打基础。

------

## 二、已完成任务与功能说明

## 1. 项目基础结构搭建

已完成项目基础目录和工程结构搭建，当前项目按照前后端、模型服务、配置文件和数据目录进行拆分。

主要完成内容包括：

- 创建项目主目录结构；
- 建立 `backend` 后端服务目录；
- 建立 `model_service` Mock 模型服务目录；
- 建立 `configs/label_configs` 标注配置目录；
- 建立 `data` 本地数据目录；
- 配置 `.gitignore`，避免提交本地数据、数据库、环境变量和模型权重；
- 配置 README 和基础运行说明；
- 建立 Git 版本管理流程，按功能分支逐步开发和提交。

当前项目已经具备较清晰的模块划分，便于后续继续交给 Codex 按任务分支开发。

------

## 2. 后端基础服务搭建

已完成 FastAPI 后端基础服务，包括接口文档、配置读取、数据库初始化和基础模块划分。

主要完成内容包括：

- 搭建 FastAPI 应用入口；
- 配置 `/docs` Swagger 接口文档；
- 建立配置管理模块；
- 建立数据库模型和基础表结构；
- 支持本地 SQLite 数据库；
- 支持从 `.env` 读取服务地址、数据目录、Label Studio 地址、模型服务地址等配置；
- 添加 CORS 配置，解决 Label Studio 页面跨域加载图片的问题。

目前后端服务可以通过以下地址访问：

```text
http://localhost:8000/docs
```

------

## 3. 数据集上传功能

已完成医学图像数据上传功能，支持通过后端接口上传图片，并在本地数据目录中保存。

主要完成内容包括：

- 支持上传单张或多张图片；
- 支持创建数据集记录；
- 自动生成 `dataset_id`；
- 将上传图片保存到本地 `data/datasets/{dataset_id}/images/` 目录；
- 记录图片文件名、路径、宽度、高度等基础信息；
- 返回数据集信息和图片列表；
- 为后续创建标注任务提供数据来源。

该功能已验证通过，上传后的图片可以通过后端媒体服务访问。

------

## 4. Label Studio 集成与任务创建功能

已完成后端与 Label Studio 的初步集成，能够自动创建 Label Studio 项目并导入图片任务。

主要完成内容包括：

- 后端读取 Label Studio 地址和 Token；
- 支持通过 Label Studio API 创建项目；
- 支持根据任务类型选择标注配置；
- 支持导入图片到 Label Studio task；
- 支持生成 Label Studio 项目访问链接；
- 支持 bbox、polygon、bbox_polygon 等任务类型；
- 支持 Label Studio 工作台中显示图片；
- 支持用户在 Label Studio 中手动画框和绘制分割轮廓。

在调试过程中解决了两个关键问题：

一是 Label Studio Token 需要通过 Personal Access Token 换取 access token 后再调用 API；
二是 Label Studio 页面加载本地后端图片时，需要后端正确配置静态文件访问和 CORS。

目前已经验证 Label Studio 中可以正常显示医学图像，并支持人工绘制检测框和分割轮廓。

------

## 5. Mock 模型服务

已完成独立的 Mock 模型服务，用于模拟后续真实 AI 模型推理过程。

主要完成内容包括：

- 在 `model_service` 中创建独立 FastAPI 服务；
- 添加 `/health` 健康检查接口；
- 添加 `/predict/detection` 检测预测接口；
- 添加 `/predict/segmentation` 分割预测接口；
- 检测接口返回固定 bbox；
- 分割接口返回固定 polygon；
- 返回统一的模型结果格式，包括 `model_id`、`model_version`、`results`、`score` 等字段；
- 不接入真实模型，不下载模型权重，保证当前阶段轻量可运行。

由于本机 `9000` 和 `9001` 端口被 MinIO 占用，模型服务当前建议使用 `9100` 端口运行：

```text
http://localhost:9100/docs
```

该模块的作用是先打通“后端调用模型服务”的接口链路，后续只需要将 Mock 逻辑替换为真实模型推理即可。

------

## 6. AI 预标注流程

已完成 AI 预标注核心流程，即后端调用 Mock 模型服务，并将模型返回结果写入 Label Studio prediction。

主要完成内容包括：

- 新增 AI 预标注 API；
- 根据 `task_id` 查询标注任务和对应图片；
- 创建预标注任务记录；
- 根据任务类型调用不同模型接口：
  - bbox 任务调用检测接口；
  - polygon 任务调用分割接口；
  - bbox_polygon 任务先调用检测，再调用分割；
- 将模型返回的 bbox 转换为 Label Studio `rectanglelabels` prediction；
- 将模型返回的 polygon 转换为 Label Studio `polygonlabels` prediction；
- 将像素坐标转换为 Label Studio 所需的百分比坐标；
- 将 prediction 写入对应的 Label Studio task；
- 更新图片预标注状态；
- 提供预标注任务状态查询接口。

该阶段完成后，系统已经具备 AI 辅助标注的核心能力：模型先给出预标注结果，用户再在 Label Studio 中进行确认和修改。

------

## 7. 标注结果导出流程

已完成标注结果导出功能，用于从 Label Studio 中拉取人工保存后的 annotation，并导出为后续训练可用的数据文件。

主要完成内容包括：

- 新增导出 API；
- 支持根据 `task_id` 发起导出任务；
- 从 Label Studio 拉取人工 annotation；
- 默认只导出人工确认后的标注结果，不导出未确认 prediction；
- 支持导出 Label Studio 原始 JSON；
- 支持导出简化 JSON；
- 支持 polygon 转换为 Mask PNG；
- 支持将导出结果打包为 zip；
- 提供 zip 文件下载接口；
- 建立导出记录，便于后续查询和管理。

该功能使系统形成了从“上传数据”到“导出训练数据”的完整闭环。

------

## 三、目前已形成的核心能力

目前 Demo 已经形成以下核心能力：

| 功能模块              | 当前状态 | 说明                                           |
| --------------------- | -------- | ---------------------------------------------- |
| 项目脚手架            | 已完成   | 已建立清晰目录结构和 Git 管理流程              |
| 后端基础服务          | 已完成   | FastAPI 服务、配置、数据库、接口文档可用       |
| 数据上传              | 已完成   | 支持上传医学图像并保存到本地                   |
| 图片静态访问          | 已完成   | 浏览器可直接访问上传图片                       |
| Label Studio 项目创建 | 已完成   | 后端可自动创建 Label Studio 项目               |
| Label Studio 图片导入 | 已完成   | 图片可导入为 Label Studio task                 |
| Label Studio 人工标注 | 已完成   | 支持手动画框和分割轮廓                         |
| Mock 检测模型服务     | 已完成   | 可返回固定 bbox                                |
| Mock 分割模型服务     | 已完成   | 可返回固定 polygon                             |
| AI 预标注             | 已完成   | 后端可调用模型服务并写入 prediction            |
| 人工确认              | 已完成   | Label Studio 中可基于 prediction 修改并 Submit |
| 标注结果导出          | 已完成   | 支持 JSON、简化 JSON、mask PNG、zip 下载       |

------

## 四、当前系统链路状态

当前已经基本完成后端 MVP 主链路：

```text
图片上传
→ 创建数据集
→ 创建标注任务
→ 自动创建 Label Studio 项目
→ 导入图片
→ 调用 Mock 模型服务
→ 生成 AI 预标注
→ 写入 Label Studio prediction
→ 人工修改并确认
→ 拉取 annotation
→ 导出训练数据
```

其中，Label Studio 作为当前阶段的标注工作台，负责图像展示、人工编辑、标注保存；后端负责数据管理、任务管理、模型服务调用和导出流程；Mock 模型服务用于模拟真实 AI 模型的预测结果。

------

## 五、当前调试与环境问题

当前主要遇到的问题集中在本地运行环境，而不是业务代码本身。

已解决的问题包括：

- PowerShell 执行策略阻止虚拟环境脚本运行；
- `uvicorn.exe` 被 PowerShell 执行策略阻止；
- Label Studio API Token 调用方式不一致；
- FastAPI 静态图片路径配置错误；
- Label Studio 页面跨域加载图片失败；
- 9000 / 9001 端口被 MinIO 占用，模型服务改用 9100；
- 8080 端口被占用时需要检查已有 Docker 容器。

当前仍需注意的问题：

- Docker Desktop 有时显示已打开，但 Docker Engine 未真正启动；
- 需要确认 `docker version` 输出中同时包含 `Client` 和 `Server`；
- 只有 `docker ps` 不报错时，才能正常启动 Label Studio；
- 若 Docker 后端异常，需要重启 Docker Desktop 或执行 `wsl --shutdown` 后重新启动。

------

## 六、当前阶段结论

目前医学 AI 辅助标注 Demo 已完成后端 MVP 的核心功能闭环，已经不只是单一接口验证，而是具备了完整的“数据进入—AI 预标注—人工确认—结果导出”流程。

当前成果可以支撑后续三个方向继续推进：

1. **前端最小页面开发**
   将 Swagger 中的上传、创建任务、预标注、导出等接口封装成简单 Web 页面，降低演示门槛。
2. **真实模型替换**
   将 Mock detection / segmentation 服务替换为真实检测模型和分割模型，实现真正的 AI 预标注。
3. **平台化功能扩展**
   在当前 MVP 基础上继续扩展任务列表、数据集管理、标注状态看板、导出记录管理、模型版本管理等功能。

总体来看，当前阶段已经完成了医学 AI 辅助标注 Demo 的核心技术验证，为后续前端联调和真实模型接入打下了基础。