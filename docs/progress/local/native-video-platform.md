# Native Video Platform Progress

## 一、当前阶段

第一阶段 MVP，本地平台窗口。服务器分支暂不存在，不阻塞本地 P0。

## 二、完成内容

- 已阅读三份项目文档并按 P0 边界执行。
- 已审计 CVAT 视频任务创建、跳转、状态同步和导出路径，见 `docs/audits/cvat-video-flow-audit.md`。
- 新视频上传默认 `annotation_backend=native`，不再创建或跳转 CVAT。
- 保留历史 CVAT API、服务、状态同步和导出代码。
- 新增平台原生视频工作台路由与页面骨架。
- 原生工作台支持短视频加载、目标创建、正点点击、Mock RLE Mask 叠加和 localStorage 最小状态恢复。
- 已冻结 `docs/contracts/medsam2-service-api-v1.md`，Mock 与 Real 使用同一请求/响应结构。
- 图片 Label Studio 代码路径未修改。

## 三、修改文件

- `backend/app/routers/videos.py`
- `backend/app/services/video_storage_service.py`
- `frontend/src/api/videos.ts`
- `frontend/src/api/medsam2.ts`
- `frontend/src/pages/UploadPage.tsx`
- `frontend/src/pages/TaskListPage.tsx`
- `frontend/src/pages/VideoDatasetDetailPage.tsx`
- `frontend/src/pages/NativeVideoWorkbenchPage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `docs/contracts/medsam2-service-api-v1.md`
- `docs/audits/cvat-video-flow-audit.md`

## 四、接口与数据变化

- Video upload `annotation_backend` now supports `native`, `cvat`, and `label_studio`.
- Default video backend is `native`.
- New frontend MedSAM2 client types define `/predict-frame` request/response and normalized row-major RLE.
- No image Label Studio task API was changed.

## 五、测试结果

- `npm run build` in `frontend/`: passed. Vite reported the existing large antd chunk warning.
- `python -m compileall backend\app`: passed.
- `git diff --check`: passed; only Git line-ending warnings were reported.
- 图片 Label Studio 回归检查：确认 `backend/app/routers/tasks.py`、`LabelStudioService`、`TaskDetailPage`、`WorkbenchPanel` 路径未改动；图片任务仍走原 `createTask` -> Label Studio 项目/任务 -> 工作台/同步/导出流程。

## 六、安全检查

- 未修改真实 MedSAM2 内部代码、CUDA 环境、服务器生产目录或生产数据库。
- 未提交视频、帧、Mask、权重、ZIP、数据库或密钥。
- 合同要求 `video_ref` 不使用绝对服务器路径。

## 七、已知问题与阻塞

- 真实 MedSAM2 服务器分支暂未发布，Real 模式接口需服务器窗口完成后联调。
- Native Mask 正式后端持久化与正式导出留到下一阶段；P0 使用 localStorage 完成刷新恢复。

## 八、读取到的对方进度

已执行 `git fetch origin`。`origin/feature/medsam2-inference-service` 暂不存在，无法读取 `docs/progress/server/medsam2-service.md`。按用户指令，本地 P0 不因此阻塞。

## 九、下一步

- 运行本地构建与基础检查。
- 修复检查发现的问题。
- 提交并 push `feature/native-video-platform`。

## 十、commit hash

提交后以 `git log -1 --oneline` 和最终汇报为准。

## 十一、git status -sb

`## feature/native-video-platform`

当前有本地待提交修改；提交后应为干净工作区。
