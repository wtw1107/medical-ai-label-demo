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
- 本地 P0 已冻结；暂不继续增加多目标、传播、画笔、正式导出等 P1/P2 功能。

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

## 五-A、本地验收步骤

1. 新建或打开 `annotation_backend=native` 的视频任务。
2. 在视频任务详情页确认展示“原生视频标注”入口。
3. 点击“进入原生标注”，确认浏览器停留在平台路由，不跳转 CVAT。
4. 确认工作台加载当前短视频，并显示视频元数据、当前帧和会话 ID。
5. 点击“创建目标”，生成稳定 `object_id`。
6. 在视频画面目标区域点击一个正点。
7. 确认页面显示正点标记，并生成半透明 Mock Mask overlay。
8. 刷新页面，确认目标、正点、当前帧和 Mock Mask 的最小会话状态可恢复。
9. 回到图片任务详情页，确认仍可通过原 Label Studio 入口打开图片标注工作台。

## 六、安全检查

- 未修改真实 MedSAM2 内部代码、CUDA 环境、服务器生产目录或生产数据库。
- 未提交视频、帧、Mask、权重、ZIP、数据库或密钥。
- 合同要求 `video_ref` 不使用绝对服务器路径。
- 已检查 commit `b77874c` 文件清单：仅包含平台代码和文档，不包含 `.mp4/.avi/.mov/.mkv`、Mask 文件、数据库、环境文件、模型权重、导出包或数据目录。
- 已对 commit `b77874c` 做敏感词检查；命中项为既有配置字段名或占位说明，例如 `LABEL_STUDIO_API_TOKEN`，未发现新增真实密钥、服务器密码、患者信息或私钥。

## 七、已知问题与阻塞

- 真实 MedSAM2 服务器分支暂未发布，Real 模式接口需服务器窗口完成后联调。
- Native Mask 正式后端持久化与正式导出留到下一阶段；P0 使用 localStorage 完成刷新恢复。

## 八、读取到的对方进度

已再次执行 `git fetch origin`。`origin/feature/medsam2-inference-service` 暂不存在，无法读取 `docs/progress/server/medsam2-service.md`。当前状态：等待服务器首次推送。按用户指令，本地 P0 不因此阻塞，不提前创建集成分支，也不修改已冻结 API 合同。

## 九、下一步

- 等服务器窗口首次 push `feature/medsam2-inference-service`。
- 服务器分支出现后，先读取 `docs/progress/server/medsam2-service.md` 和服务器实现接口。
- 不提前创建集成分支；不部署生产；不删除历史 CVAT 代码。

## 十、commit hash

提交后以 `git log -1 --oneline` 和最终汇报为准。

## 十一、git status -sb

`## feature/native-video-platform`

当前有本地待提交修改；提交后应为干净工作区。
