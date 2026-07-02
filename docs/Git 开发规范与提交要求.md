# Git 开发规范与提交要求

## 一、当前开发原则

当前项目已经有一条跑通的本地 MVP 闭环，后续开发必须采用增量开发方式。

不要直接在已有稳定代码上混杂开发大功能。每一阶段都应新建功能分支，完成后本地验证，通过后再提交。

------

## 二、每次开发前必须确认当前分支状态

开发前先确认：

1. 当前在哪个分支；
2. 当前分支是否有未提交修改；
3. 最近一次提交是什么；
4. 是否需要先提交当前工作再切新分支。

推荐命令：

```bash
git branch --show-current
git status -sb
```

如果只想确认当前分支是否已经干净、所有修改是否已提交，可以运行：

```bash
test -z "$(git status --porcelain)" && echo "✅ clean: 当前分支没有未提交修改" || git status --short
```

判断标准：

```text
如果输出：
✅ clean: 当前分支没有未提交修改

说明当前工作区是干净的，可以创建新分支继续开发。

如果输出了 M / A / D / ?? 等文件列表，
说明当前还有未提交修改，需要先确认是否提交、暂存或丢弃。
```

------

## 三、推荐分支策略

当前阶段建议从当前稳定分支切出新的功能分支。

### 阶段一分支

```bash
git checkout -b feature/embed-label-studio-workbench
```

用途：

```text
Label Studio 内嵌前端
图像级标注入口
基础 iframe 工作台
```

------

### 阶段二分支

```bash
git checkout -b feature/status-sync-and-ai-preview
```

用途：

```text
同步 Label Studio 状态
AI prediction 只读预览
导出面板增强
```

------

### 阶段三分支

```bash
git checkout -b feature/real-model-integration
```

用途：

```text
真实检测模型接入
真实分割模型接入
mock / real 模型切换
Label Studio labeling config 增强
AI 元数据追溯
```

------

## 四、每个阶段开发前流程

每次开始新阶段前执行：

```bash
git branch --show-current
test -z "$(git status --porcelain)" && echo "✅ clean: 当前分支没有未提交修改" || git status --short
```

如果工作区干净，再创建新分支：

```bash
git checkout -b feature/embed-label-studio-workbench
```

开发过程中可以随时查看修改：

```bash
git status -sb
git diff --stat
```

------

## 五、每个阶段提交前检查

提交前建议执行：

```bash
git status -sb
git diff --stat
```

如果前端有 build script，执行：

```bash
npm run build
```

如果后端有测试或基础启动检查，执行对应命令，例如：

```bash
python -m compileall .
```

或项目已有的测试命令。

------

## 六、提交规范

每个阶段只提交与本阶段有关的改动。

提交信息建议格式：

```bash
git add .
git commit -m "feat(frontend): embed label studio workbench"
```

阶段一推荐提交信息：

```bash
git commit -m "feat(frontend): embed label studio workbench in task detail"
```

阶段二推荐提交信息：

```bash
git commit -m "feat(frontend): add label studio status sync and prediction preview"
```

阶段三推荐提交信息：

```bash
git commit -m "feat(model): integrate real detection and segmentation models"
```

------

## 七、开发边界

任何阶段都不要做以下事情：

1. 不要删除现有 mock 模型；
2. 不要破坏当前上传流程；
3. 不要破坏当前 AI 预标注流程；
4. 不要破坏当前导出流程；
5. 不要重写 Label Studio 标注画布；
6. 不要 fork 或源码级修改 Label Studio；
7. 不要引入登录、权限、多人协作；
8. 不要引入 DICOM、3D、视频；
9. 不要把本地数据、上传图片、导出 zip、node_modules、模型权重提交到 Git；
10. 不要一次性开发多个阶段的功能。

------

## 八、本阶段最重要的 Git 命令

开始阶段一前，先运行：

```bash
git branch --show-current
test -z "$(git status --porcelain)" && echo "✅ clean: 当前分支没有未提交修改" || git status --short
```

确认 clean 后，再运行：

```bash
git checkout -b feature/embed-label-studio-workbench
```