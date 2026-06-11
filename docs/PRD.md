# 医学影像 AI 辅助标注 Demo PRD

## 基于 Label Studio 的轻量实现方案

版本：V1.0
产品形态：轻量级 Web Demo + Label Studio 标注工作台 + 自定义模型服务
适用阶段：原型验证 / 小范围演示 / 私有医学数据标注流程验证

------

# 1. 产品背景

医学影像数据标注高度依赖医生或专业标注人员，尤其是病灶检测框、病灶边缘轮廓、分割 Mask 等任务，存在以下问题：

1. 标注成本高；
2. 标注周期长；
3. 私有医院数据通常没有现成标注；
4. 通用模型很难直接对所有医学图像稳定输出高质量标注；
5. 医生更适合做审核、修正和困难样本判断，而不是从零逐张标注。

因此，本 Demo 不追求“AI 完全自动替代人工标注”，而是实现一个更真实、可落地的轻量闭环：

> 上传医学图像后，系统调用检测或分割模型生成候选预标注，人工在 Label Studio 工作台中对 bbox、polygon、mask 进行审核、修正和确认，最终将确认后的结果导出为 JSON、Mask、COCO 或 YOLO 等训练可用格式。

------

# 2. 产品定位

## 2.1 产品名称

医学影像 AI 辅助标注 Demo

## 2.2 产品定位

本产品是一个基于 Label Studio 的轻量级医学影像 AI 辅助标注工具，用于验证以下能力：

1. 医学图像数据上传；
2. 检测模型 / 分割模型接入；
3. AI 生成候选预标注；
4. 人工审核、修正与确认；
5. 标注结果导出；
6. 后续可扩展为少样本适配和批量预标注流程。

## 2.3 产品不做什么

第一阶段不做完整平台化系统，不做复杂权限体系和完整训练平台。

暂不包含：

1. 完整用户权限系统；
2. 多角色任务分配；
3. 医生工作量统计；
4. 完整主动学习看板；
5. DICOM 影像管理；
6. 3D 医学影像标注；
7. 视频标注；
8. 大规模训练调度；
9. 模型版本生命周期管理；
10. 临床诊断或诊疗结论生成。

------

# 3. 产品目标

## 3.1 业务目标

1. 降低医学影像标注从零开始的成本；
2. 让 AI 预标注成为人工标注的起点；
3. 支持检测框和分割轮廓两类核心标注任务；
4. 形成“AI 预标注 → 人工修正 → 标注导出”的最小闭环；
5. 为后续接入私有医院数据、训练专用模型和批量预标注打基础。

## 3.2 Demo 目标

第一阶段 Demo 需要能够演示：

1. 上传一批医学图像；
2. 选择检测框任务或分割任务；
3. 调用已接入模型生成预标注；
4. 在 Label Studio 中查看 AI 预标注结果；
5. 人工修改检测框或分割轮廓；
6. 人工确认结果；
7. 导出 JSON、Mask 或检测格式文件。

## 3.3 评估目标

Demo 成功的标准不是 AI 一次性标注全部准确，而是：

1. 能够自动生成可见的候选标注；
2. 人工可以在工作台中修改候选结果；
3. 修改后的结果可以保存为正式 annotation；
4. 确认后的结果可以导出；
5. 整个流程可在 3–5 分钟内讲清楚。

------

# 4. 用户与使用场景

## 4.1 目标用户

| 用户类型        | 角色说明                               | 核心诉求               |
| --------------- | -------------------------------------- | ---------------------- |
| 算法工程师      | 负责模型接入、预标注生成、导出训练数据 | 快速获得可训练标注数据 |
| 医学标注人员    | 负责修正 AI 预标注结果                 | 减少从零标注工作量     |
| 医生 / 审核人员 | 负责确认标注质量                       | 快速检查和修正关键区域 |
| 平台开发人员    | 负责系统集成和接口开发                 | 低成本集成现有标注能力 |

## 4.2 典型场景

### 场景 1：私有医院数据冷启动

医院提供一批未标注的甲状腺、乳腺或其他超声图像。平台没有该数据集专用模型，用户先使用通用医学分割模型或相近模型生成候选结果，医生修正一小批样本，形成种子标注。

### 场景 2：已有检测模型辅助标注

算法团队已有一个基于相近数据训练过的检测模型。用户上传新图像后，模型生成病灶 bbox，标注人员只需要检查框的位置并调整错误结果。

### 场景 3：检测框引导分割

系统先用检测模型生成病灶框，再基于 bbox 调用分割模型生成初始 Mask，人工只修正边缘轮廓。

### 场景 4：导出训练数据

人工确认后的标注结果导出为 JSON、COCO、YOLO 或 Mask PNG，用于后续模型训练。

------

# 5. 核心用户流程

## 5.1 主流程

```text
进入 Demo 首页
→ 上传医学图像 / 压缩包
→ 创建标注任务
→ 选择任务类型：检测框 / 分割轮廓 / 检测框+分割
→ 选择 AI 辅助方式或模型
→ 系统生成预标注
→ 进入 Label Studio 标注工作台
→ 人工审核、修正、确认
→ 保存正式 annotation
→ 导出结果
```

## 5.2 检测框任务流程

```text
上传图像
→ 选择病灶检测框任务
→ 选择检测模型
→ AI 生成 bbox 预标注
→ 人工检查 bbox
→ 调整 bbox 位置和大小
→ 删除错误框或新增漏标框
→ 点击确认
→ 导出 JSON / COCO / YOLO
```

## 5.3 分割轮廓任务流程

```text
上传图像
→ 选择分割轮廓任务
→ 选择通用医学分割模型或专用分割模型
→ AI 生成 polygon / mask 预标注
→ 人工检查边界
→ 使用 polygon、画笔或橡皮擦修正
→ 点击确认
→ 导出 JSON / Mask PNG / COCO Segmentation
```

## 5.4 检测框 + 分割组合流程

```text
上传图像
→ 选择检测框 + 分割组合任务
→ 检测模型生成 bbox
→ 分割模型基于 bbox 生成初始 mask
→ 人工调整 bbox 和 mask
→ 确认结果
→ 导出 bbox + mask
```

------

# 6. 功能范围

## 6.1 功能范围总览

| 模块           | 功能                               | 优先级 |
| -------------- | ---------------------------------- | ------ |
| 数据上传       | 图片 / 压缩包上传                  | P0     |
| 任务创建       | 选择任务类型、模型、标注配置       | P0     |
| AI 预标注      | 调用模型生成 bbox / polygon / mask | P0     |
| 标注工作台     | 基于 Label Studio 修改和确认结果   | P0     |
| 结果保存       | 保存人工确认后的 annotation        | P0     |
| 结果导出       | 导出 JSON、COCO、YOLO、Mask        | P0     |
| 导出转换       | Label Studio JSON 转 Mask PNG      | P1     |
| 标注状态管理   | 待确认、已修正、已确认             | P1     |
| 模型配置管理   | 管理模型名称、版本、接口地址       | P1     |
| 少样本适配入口 | 种子标注训练提示                   | P2     |
| 主动学习排序   | 高风险样本优先处理                 | P2     |

------

# 7. 页面结构

第一阶段建议只做 4 个页面。

```text
P01 数据上传与任务创建页
P02 AI 预标注结果页
P03 Label Studio 标注修正工作台
P04 标注结果导出页
```

其中 P03 可直接复用 Label Studio 工作台，外层只做跳转和流程包装。

------

# 8. 页面需求

## P01 数据上传与任务创建页

### 8.1 页面目标

让用户上传医学图像，并选择标注任务类型和 AI 辅助方式。

### 8.2 页面模块

1. 页面标题区；
2. 数据上传区；
3. 上传文件列表；
4. 任务类型选择；
5. 模型选择；
6. AI 辅助方式说明；
7. 创建任务并生成预标注按钮。

### 8.3 字段设计

#### 数据上传字段

| 字段       | 类型     | 说明                               |
| ---------- | -------- | ---------------------------------- |
| 数据集名称 | Input    | 用户自定义，如“甲状腺超声测试数据” |
| 上传文件   | Upload   | 支持单张、多张或 zip               |
| 数据类型   | Select   | 超声图像，第一阶段默认             |
| 文件格式   | 自动识别 | PNG、JPG、JPEG                     |
| 图像数量   | 自动统计 | 上传后展示                         |
| 上传状态   | 自动展示 | 上传中、成功、失败                 |

#### 任务配置字段

| 字段                 | 类型           | 说明                          |
| -------------------- | -------------- | ----------------------------- |
| 任务名称             | Input          | 默认根据数据集名称生成        |
| 标注任务类型         | Radio / Card   | 检测框、分割轮廓、检测框+分割 |
| 标注对象             | Input / Select | 如病灶、结节、目标区域        |
| 标签名称             | Input          | 如“病灶”“甲状腺结节”          |
| 是否需要人工确认     | Switch         | 默认开启且不可关闭            |
| 是否保留 AI 来源信息 | Switch         | 默认开启                      |

#### 模型选择字段

| 字段        | 类型     | 说明                                       |
| ----------- | -------- | ------------------------------------------ |
| AI 辅助方式 | Radio    | 通用模型辅助、相近模型预标注、已有专用模型 |
| 检测模型    | Select   | YOLO、DINO、UQ-DINO 等                     |
| 分割模型    | Select   | SAM、MedSAM、专用分割模型                  |
| 模型版本    | 自动展示 | 如 v1.0                                    |
| 模型状态    | 自动展示 | 可用、不可用、加载中                       |
| 预标注方式  | Radio    | 自动批量预标注 / 进入工作台时按需预测      |

### 8.4 交互规则

1. 未上传图像时，不允许创建任务；
2. 未选择任务类型时，不允许创建任务；
3. 选择“检测框任务”时，必须选择检测模型或选择手动标注；
4. 选择“分割任务”时，必须选择分割模型或选择手动标注；
5. 选择“检测框 + 分割”时，可选择检测模型与分割模型；
6. 点击“生成 AI 预标注”后，进入 P02；
7. 如果模型不可用，页面提示“当前模型不可用，可先创建纯人工任务”。

------

## P02 AI 预标注结果页

### 8.5 页面目标

展示 AI 预标注处理进度和结果状态，让用户进入人工修正工作台。

### 8.6 页面模块

1. 任务信息卡；
2. 预标注进度条；
3. 统计卡片；
4. 图像结果列表；
5. 错误列表；
6. 进入人工修正按钮。

### 8.7 字段设计

#### 任务信息卡

| 字段     | 示例                       |
| -------- | -------------------------- |
| 任务名称 | 甲状腺超声 AI 辅助标注任务 |
| 数据集   | 甲状腺超声测试数据         |
| 图像数量 | 120                        |
| 任务类型 | 检测框 + 分割              |
| 检测模型 | Thyroid-YOLO-v1            |
| 分割模型 | MedSAM-v1                  |
| 创建时间 | 2026-06-11 14:00           |

#### 统计卡片

| 指标       | 说明                     |
| ---------- | ------------------------ |
| 总图像数   | 当前任务内全部图像       |
| 预标注成功 | 已生成候选结果的图像数量 |
| 预标注失败 | 模型调用失败或无结果     |
| 待人工确认 | 需要进入工作台确认的数量 |
| 已确认     | 人工保存正式标注的数量   |

#### 图像结果列表字段

| 字段         | 说明                       |
| ------------ | -------------------------- |
| 图像缩略图   | 展示原图                   |
| 图像名称     | 文件名                     |
| 预标注状态   | 未处理、处理中、成功、失败 |
| bbox 数量    | 检测框数量                 |
| mask 数量    | 分割结果数量               |
| AI 来源      | 模型名称与版本             |
| 人工确认状态 | 待确认、已确认             |
| 操作         | 查看、进入修正、重新生成   |

### 8.8 交互规则

1. 预标注进行中显示进度；
2. 预标注完成后可进入 Label Studio；
3. 单张失败可点击“重新生成”；
4. 如果全部失败，可提示检查模型服务；
5. 点击“进入人工修正”跳转 P03；
6. P02 应明确提示：“AI 结果为候选预标注，需人工确认后才能导出为正式标注”。

------

## P03 Label Studio 标注修正工作台

### 8.9 页面目标

使用 Label Studio 原生工作台完成 bbox、polygon、mask 的人工审核、修正和确认。

### 8.10 Label Studio 标注配置

根据任务类型生成不同 labeling config。

#### 检测框配置

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="true"/>
  <Header value="病灶区域检测框"/>
  <RectangleLabels name="bbox" toName="image">
    <Label value="病灶" background="#21C7C4"/>
  </RectangleLabels>
  <Choices name="review_status" toName="image" choice="single">
    <Choice value="通过"/>
    <Choice value="需要重标"/>
    <Choice value="无法判断"/>
  </Choices>
  <TextArea name="review_comment" toName="image" placeholder="填写审核意见或修正说明"/>
</View>
```

#### 分割轮廓配置

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="true"/>
  <Header value="病灶轮廓分割"/>
  <PolygonLabels name="lesion_polygon" toName="image">
    <Label value="病灶轮廓" background="#FBBF24"/>
  </PolygonLabels>
  <Choices name="review_status" toName="image" choice="single">
    <Choice value="通过"/>
    <Choice value="需要重标"/>
    <Choice value="无法判断"/>
  </Choices>
  <TextArea name="review_comment" toName="image" placeholder="填写审核意见或修正说明"/>
</View>
```

#### 检测框 + 分割组合配置

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="true"/>
  
  <Header value="病灶区域检测框"/>
  <RectangleLabels name="bbox" toName="image">
    <Label value="病灶" background="#21C7C4"/>
  </RectangleLabels>

  <Header value="病灶轮廓分割"/>
  <PolygonLabels name="lesion_polygon" toName="image">
    <Label value="病灶轮廓" background="#FBBF24"/>
  </PolygonLabels>

  <Choices name="review_status" toName="image" choice="single">
    <Choice value="通过"/>
    <Choice value="需要重标"/>
    <Choice value="无法判断"/>
  </Choices>

  <TextArea name="review_comment" toName="image" placeholder="填写审核意见或修正说明"/>
</View>
```

### 8.11 工作台能力要求

| 能力                | 实现方式                     |
| ------------------- | ---------------------------- |
| 查看 AI 预标注 bbox | Label Studio predictions     |
| 修改 bbox           | Label Studio RectangleLabels |
| 新增 bbox           | Label Studio RectangleLabels |
| 删除 bbox           | Label Studio 原生操作        |
| 查看 AI polygon     | Label Studio predictions     |
| 修改 polygon        | Label Studio PolygonLabels   |
| 新增 polygon        | Label Studio PolygonLabels   |
| 审核状态            | Choices 字段                 |
| 审核意见            | TextArea 字段                |
| 保存正式结果        | Label Studio annotation      |

### 8.12 状态规则

| 状态       | 含义                   |
| ---------- | ---------------------- |
| prediction | AI 预标注结果          |
| annotation | 人工确认后的正式标注   |
| 通过       | 当前图像标注可导出     |
| 需要重标   | 当前图像需重新处理     |
| 无法判断   | 当前图像不进入正式导出 |

### 8.13 交互规则

1. AI 预标注作为 prediction 显示；
2. 用户必须保存 annotation 才视为人工确认；
3. 用户可修改 prediction 后保存为 annotation；
4. 未保存 annotation 的任务不进入正式导出范围；
5. 选择“需要重标”的图像可在 P02 中显示为需重标状态；
6. 选择“无法判断”的图像默认不进入训练数据导出。

------

## P04 标注结果导出页

### 8.14 页面目标

将人工确认后的 annotation 导出为训练可用格式。

### 8.15 页面模块

1. 标注完成统计；
2. 导出范围选择；
3. 导出格式选择；
4. 导出配置；
5. 导出记录；
6. 下载结果。

### 8.16 字段设计

#### 标注统计

| 字段       | 说明                               |
| ---------- | ---------------------------------- |
| 总图像数   | 任务内全部图像                     |
| 已确认图像 | 已保存 annotation 且审核状态为通过 |
| 需要重标   | 审核状态为需要重标                 |
| 无法判断   | 审核状态为无法判断                 |
| 可导出图像 | 默认等于已确认图像                 |

#### 导出范围

| 选项           | 说明                          |
| -------------- | ----------------------------- |
| 全部已确认     | 默认选项                      |
| 当前选中图像   | 用户手动选择                  |
| 按审核状态导出 | 只导出通过 / 包含无法判断     |
| 按标注类型导出 | 仅 bbox / 仅 mask / bbox+mask |

#### 导出格式

| 格式              | 用途            | 优先级 |
| ----------------- | --------------- | ------ |
| Label Studio JSON | 原始标注结果    | P0     |
| 简化 JSON         | 平台内部使用    | P0     |
| COCO JSON         | 检测 / 分割训练 | P0     |
| YOLO TXT          | 检测训练        | P1     |
| Mask PNG          | 分割训练        | P1     |
| LabelMe JSON      | 标注工具兼容    | P1     |

### 8.17 导出规则

1. 默认只导出人工确认且审核状态为“通过”的图像；
2. 未确认 prediction 不导出为正式结果；
3. Mask PNG 由 polygon 或 brush 结果转换生成；
4. 导出文件需打包为 zip；
5. 导出记录保留导出时间、格式、图像数量和操作人；
6. 导出失败时显示失败原因。

------

# 9. 数据状态设计

## 9.1 图像级状态

```text
已上传
→ 待预标注
→ 预标注中
→ 预标注完成
→ 待人工确认
→ 已确认
→ 可导出
```

异常分支：

```text
预标注失败
需要重标
无法判断
```

## 9.2 标注结果状态

| 状态       | 说明                     |
| ---------- | ------------------------ |
| AI 预标注  | 模型生成的 prediction    |
| 人工已修改 | prediction 被人工调整    |
| 人工已确认 | 已保存为 annotation      |
| 审核通过   | review_status = 通过     |
| 需要重标   | review_status = 需要重标 |
| 无法判断   | review_status = 无法判断 |

## 9.3 关键业务规则

1. AI prediction 不能直接作为最终导出结果；
2. annotation 才是正式标注结果；
3. 标注结果必须包含来源信息；
4. 导出时默认排除未确认和无法判断图像；
5. 每次模型预测需记录模型名称和版本。

------

# 10. 技术方案

## 10.1 总体架构

```text
自研轻量 Demo 前端
  ├── 数据上传页
  ├── 预标注结果页
  └── 导出页

Label Studio
  ├── 项目管理
  ├── 标注工作台
  ├── prediction 展示
  └── annotation 保存

自定义后端服务
  ├── 文件上传
  ├── Label Studio API 封装
  ├── 任务创建
  ├── 模型调用
  ├── 结果导出
  └── 格式转换

ML Backend / 模型服务
  ├── 检测模型服务
  ├── 分割模型服务
  └── prediction 格式转换
```

## 10.2 组件职责

### 自研 Demo 前端

负责：

1. 上传入口；
2. 任务创建表单；
3. 预标注状态展示；
4. 跳转 Label Studio；
5. 导出配置页面；
6. Demo 风格包装。

### Label Studio

负责：

1. 图像标注工作台；
2. bbox 标注；
3. polygon / brush 标注；
4. prediction 展示；
5. annotation 保存；
6. 原始 JSON 导出。

### 自定义后端

负责：

1. 接收上传文件；
2. 解压 zip；
3. 保存图片；
4. 调用 Label Studio API 创建项目和任务；
5. 连接 ML Backend；
6. 拉取 annotation；
7. 转换导出格式；
8. 生成 Mask PNG；
9. 打包下载文件。

### ML Backend

负责：

1. 加载检测模型；
2. 加载分割模型；
3. 接收 Label Studio 的预测请求；
4. 读取图像；
5. 输出 bbox / polygon / mask；
6. 转换为 Label Studio predictions 格式；
7. 返回模型版本和预测分数。

------

# 11. 技术要求

## 11.1 Label Studio 部署要求

建议使用 Docker 部署。

基础要求：

1. Label Studio 服务；
2. PostgreSQL 数据库，Demo 阶段可先使用默认存储；
3. 文件存储目录挂载；
4. 可访问的图片 URL 或本地文件路径；
5. API Token 用于自研后端调用。

## 11.2 后端技术要求

推荐技术栈：

| 模块             | 建议                     |
| ---------------- | ------------------------ |
| Web 框架         | FastAPI                  |
| 文件处理         | Python pathlib / zipfile |
| 图像处理         | OpenCV / Pillow          |
| Mask 转换        | OpenCV / NumPy           |
| Label Studio API | requests / httpx         |
| 打包下载         | zipfile                  |
| 模型服务         | PyTorch / ONNX Runtime   |

## 11.3 前端技术要求

推荐技术栈：

| 模块       | 建议                                    |
| ---------- | --------------------------------------- |
| 前端框架   | Vue 3 或 React                          |
| UI 组件    | Ant Design Vue / Naive UI / Arco Design |
| 文件上传   | Upload 组件                             |
| 状态展示   | Table + Tag + Progress                  |
| 跳转工作台 | 新页面打开 Label Studio URL             |
| 导出下载   | 调用后端导出接口                        |

## 11.4 模型输出格式要求

### bbox 输出

模型输出原始格式：

```json
{
  "label": "病灶",
  "x": 120,
  "y": 80,
  "width": 164,
  "height": 148,
  "score": 0.91
}
```

转换为 Label Studio 百分比格式：

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

### polygon 输出

模型输出原始格式：

```json
{
  "label": "病灶轮廓",
  "points": [[120, 80], [135, 76], [160, 92]],
  "score": 0.86
}
```

转换为 Label Studio 百分比格式：

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

# 12. API 需求

## 12.1 自研后端 API

### 上传数据

```http
POST /api/demo/datasets/upload
```

功能：

1. 上传图片或 zip；
2. 解压文件；
3. 生成数据集记录；
4. 返回图片列表。

返回：

```json
{
  "dataset_id": "ds_001",
  "image_count": 120,
  "images": [
    {
      "id": "img_001",
      "filename": "thyroid_001.png",
      "url": "/media/ds_001/thyroid_001.png"
    }
  ]
}
```

### 创建标注任务

```http
POST /api/demo/annotation-tasks
```

请求：

```json
{
  "dataset_id": "ds_001",
  "task_name": "甲状腺超声 AI 辅助标注任务",
  "task_type": "bbox_mask",
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

### 生成 AI 预标注

```http
POST /api/demo/annotation-tasks/{task_id}/prelabel
```

返回：

```json
{
  "task_id": "task_001",
  "status": "running",
  "total": 120,
  "processed": 0
}
```

### 查询预标注状态

```http
GET /api/demo/annotation-tasks/{task_id}/prelabel-status
```

返回：

```json
{
  "status": "completed",
  "total": 120,
  "success": 112,
  "failed": 8,
  "pending_confirm": 112
}
```

### 获取工作台链接

```http
GET /api/demo/annotation-tasks/{task_id}/label-studio-url
```

返回：

```json
{
  "url": "http://localhost:8080/projects/12/data"
}
```

### 导出结果

```http
POST /api/demo/annotation-tasks/{task_id}/export
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

### 下载导出文件

```http
GET /api/demo/exports/{export_id}/download
```

返回：

```json
{
  "download_url": "/downloads/export_001.zip"
}
```

------

# 13. 模型接入要求

## 13.1 检测模型

第一阶段可支持任一检测模型：

1. YOLO；
2. DINO；
3. Faster R-CNN；
4. 自定义 PyTorch 模型。

输出要求：

1. bbox 坐标；
2. 类别；
3. score；
4. 模型版本。

## 13.2 分割模型

第一阶段可支持：

1. SAM；
2. MedSAM；
3. U-Net；
4. nnU-Net；
5. 自定义分割模型。

输出要求：

1. mask 或 polygon；
2. 类别；
3. score；
4. 模型版本。

## 13.3 模型调用策略

支持两种方式：

### 方式 A：Label Studio ML Backend 调用

适合与 Label Studio 原生集成。

```text
Label Studio → ML Backend → 返回 predictions
```

### 方式 B：自研后端批量调用模型后导入 predictions

适合 Demo 可控流程。

```text
自研后端 → 模型服务 → 生成 predictions → 写入 Label Studio 项目
```

第一阶段建议优先采用方式 B，流程更容易控制，也更适合“上传后批量生成预标注结果”的 Demo 叙事。

------

# 14. 导出转换要求

## 14.1 Label Studio JSON

直接导出 Label Studio 原始 JSON，用于追溯所有 prediction 和 annotation。

## 14.2 简化 JSON

建议转换为平台内部统一格式：

```json
{
  "image": "thyroid_001.png",
  "width": 677,
  "height": 432,
  "objects": [
    {
      "label": "病灶",
      "bbox": [120, 80, 164, 148],
      "polygon": [[120, 80], [135, 76]],
      "source": "human_confirmed",
      "model_version": "thyroid_yolo_v1"
    }
  ]
}
```

## 14.3 Mask PNG

转换规则：

1. 读取 polygon 点；
2. 根据原图尺寸还原像素坐标；
3. 使用 OpenCV 填充 polygon；
4. 输出二值 mask；
5. 每张图对应一个 mask 文件。

## 14.4 COCO JSON

需要支持：

1. images；
2. annotations；
3. categories；
4. bbox；
5. segmentation；
6. area；
7. iscrowd。

## 14.5 YOLO TXT

每个 bbox 转为：

```text
class_id x_center y_center width height
```

其中坐标为归一化比例。

------

# 15. 验收标准

## 15.1 功能验收

| 编号 | 验收项                 | 标准                              |
| ---- | ---------------------- | --------------------------------- |
| A01  | 上传图片               | 可上传单张、多张或 zip            |
| A02  | 创建任务               | 可选择检测框、分割或组合任务      |
| A03  | 创建 Label Studio 项目 | 后端能自动创建项目和任务          |
| A04  | 生成预标注             | 至少能生成 bbox 或 polygon 预标注 |
| A05  | 显示预标注             | Label Studio 中能看到 prediction  |
| A06  | 人工修正               | 可修改 bbox 或 polygon            |
| A07  | 保存 annotation        | 人工确认结果能保存                |
| A08  | 状态统计               | 能区分待确认、已确认、失败        |
| A09  | 导出 JSON              | 能导出人工确认后的 JSON           |
| A10  | 导出 Mask              | polygon 可转为 mask PNG           |
| A11  | 导出压缩包             | 导出结果可下载                    |
| A12  | 模型版本记录           | 预标注结果保留模型版本信息        |

## 15.2 演示验收

Demo 演示需完成：

```text
上传 5–20 张医学图像
→ 选择检测框+分割任务
→ 生成 AI 预标注
→ 打开 Label Studio
→ 修改一张图的 bbox 或 polygon
→ 保存 annotation
→ 返回导出页
→ 导出 JSON 或 mask
```

## 15.3 边界验收

1. 模型服务不可用时，前端有明确提示；
2. 单张图像预标注失败不影响其他图像；
3. 未人工确认的 prediction 不进入正式导出；
4. 没有 polygon 的图像不能导出 mask；
5. zip 中存在非图片文件时自动跳过或提示。

------

# 16. 里程碑计划

## 阶段 1：Label Studio 基础联通

目标：

1. Docker 启动 Label Studio；
2. 手动创建项目；
3. 配置 bbox / polygon 标注模板；
4. 上传图片；
5. 手动完成标注并导出 JSON。

交付物：

1. Label Studio 可运行环境；
2. 基础 labeling config；
3. 手动标注流程验证。

## 阶段 2：自研上传与项目创建

目标：

1. 自研上传页；
2. 后端接收图片；
3. 自动创建 Label Studio 项目；
4. 自动导入任务；
5. 返回工作台链接。

交付物：

1. 上传页面；
2. FastAPI 后端；
3. Label Studio API 封装。

## 阶段 3：AI 预标注接入

目标：

1. 接入检测模型；
2. 接入分割模型；
3. 生成 Label Studio predictions；
4. 在工作台显示 bbox / polygon 预标注。

交付物：

1. ML Backend 或模型调用服务；
2. prediction 转换模块；
3. 预标注结果页。

## 阶段 4：人工确认与导出

目标：

1. 获取 Label Studio annotation；
2. 筛选通过结果；
3. 导出 JSON；
4. polygon 转 mask；
5. 打包下载。

交付物：

1. 导出页面；
2. JSON 转换脚本；
3. Mask PNG 导出脚本；
4. 下载接口。

## 阶段 5：演示优化

目标：

1. 简化页面流程；
2. 增加 Demo 说明文案；
3. 增加模型不可用提示；
4. 准备测试数据；
5. 准备演示脚本。

交付物：

1. 可演示 Demo；
2. 测试数据；
3. 演示说明文档。

------

# 17. 风险与应对

## 17.1 模型直接预标注效果不稳定

风险：

通用模型或未经当前私有数据适配的模型可能无法稳定标注病灶。

应对：

1. 页面中明确 AI 结果为候选预标注；
2. 强制人工确认；
3. 优先展示“辅助修正”而非“自动完成”；
4. 后续引入少样本适配训练。

## 17.2 Label Studio UI 与自研平台风格不一致

风险：

工作台视觉风格不完全可控。

应对：

1. 第一阶段接受原生工作台；
2. 外层上传页和导出页做成自研风格；
3. 后续如有必要再做前端源码二开。

## 17.3 Mask 导出格式复杂

风险：

Label Studio 原始 JSON 需要额外转换才能生成训练用 mask。

应对：

1. 第一阶段先支持 polygon 转 mask；
2. brush mask 作为后续扩展；
3. 明确统一输出二值 mask PNG。

## 17.4 图片路径访问问题

风险：

Label Studio、后端、模型服务之间可能因路径或 URL 不一致导致图片无法读取。

应对：

1. 统一文件存储目录；
2. 后端生成可访问 URL；
3. 模型服务通过统一 URL 或共享挂载目录读取图片。

## 17.5 私有医院数据安全问题

风险：

真实医院数据涉及隐私和合规。

应对：

1. Demo 阶段使用脱敏或公开样例数据；
2. 未来接入私有数据时增加权限、日志和本地化部署；
3. 不上传真实隐私数据到外部服务。

------

# 18. 后续扩展方向

第一阶段完成后，可逐步扩展：

1. 支持 DICOM；
2. 支持医生审核角色；
3. 支持任务分配；
4. 支持模型版本管理；
5. 支持少样本适配训练；
6. 支持主动学习样本排序；
7. 支持不确定性区域提示；
8. 支持多部位医学影像模板；
9. 支持平台账号单点登录；
10. 支持与 EPAI 训练模块打通。

------

# 19. 一句话总结

本项目第一阶段要实现一个基于 Label Studio 的轻量医学影像 AI 辅助标注 Demo：用户上传医学图像后，系统调用检测或分割模型生成候选预标注，人工在 Label Studio 中对 bbox、polygon 或 mask 进行审核、修正和确认，最终将确认后的结果导出为 JSON、Mask、COCO 或 YOLO 等训练可用格式。AI 不直接替代人工，而是作为预标注和交互式修正工具，降低医学私有数据从零标注的成本。