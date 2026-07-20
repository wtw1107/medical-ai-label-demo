import React from "react";
import { FolderOpenOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, Input, Select, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listTasks } from "../api/tasks";
import { listVideoDatasets } from "../api/videos";
import type { AnnotationTaskListItem, TaskType, VideoDatasetListItem } from "../types/api";

type DataTypeFilter = "all" | "image" | "video";
type ToolFilter = "all" | "label_studio" | "native_video" | "cvat" | "label_studio_legacy";
type StatusGroup = "all" | "pending" | "in_progress" | "review" | "completed" | "problem" | "unavailable";
type SortMode = "updated_desc" | "updated_asc" | "created_desc" | "name_asc";

interface UnifiedTaskItem {
  id: string;
  name: string;
  dataType: "image" | "video";
  taskType: TaskType;
  datasetName: string;
  itemCount: number;
  annotationBackend: "label_studio" | "native_video" | "cvat";
  toolLabel: string;
  status: string;
  statusLabel: string;
  statusGroup: Exclude<StatusGroup, "all">;
  createdAt?: string | null;
  updatedAt?: string | null;
  detailPath: string;
  legacy?: boolean;
}

const taskTypeLabels: Record<TaskType, string> = {
  bbox: "目标框标注",
  polygon: "多边形分割",
  bbox_polygon: "目标框 + 多边形",
  video_bline_segmentation: "B-line 视频分割",
};

const statusGroupLabels: Record<Exclude<StatusGroup, "all">, string> = {
  pending: "待处理",
  in_progress: "标注中",
  review: "待复核",
  completed: "已完成",
  problem: "存在问题",
  unavailable: "服务不可用",
};

function parseTime(value?: string | null) {
  if (!value) {
    return Number.NaN;
  }
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? Number.NaN : timestamp;
}

function sortTime(value?: string | null) {
  const timestamp = parseTime(value);
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp;
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function normalizeImageStatus(status: string): { label: string; group: UnifiedTaskItem["statusGroup"] } {
  const normalized = status.toLowerCase();
  if (["completed", "done", "finished", "exported"].some((item) => normalized.includes(item))) {
    return { label: "已完成", group: "completed" };
  }
  if (["failed", "error", "invalid"].some((item) => normalized.includes(item))) {
    return { label: "存在问题", group: "problem" };
  }
  if (["created", "pending", "queued", "new"].some((item) => normalized.includes(item))) {
    return { label: "待处理", group: "pending" };
  }
  return { label: "标注中", group: "in_progress" };
}

function normalizeVideoStatus(record: VideoDatasetListItem): { label: string; group: UnifiedTaskItem["statusGroup"] } {
  if (record.annotation_backend === "label_studio") {
    return { label: "旧版流程", group: "in_progress" };
  }
  if (record.annotation_backend === "cvat") {
    if (record.video_count > 0 && record.initialized_video_count === 0) {
      return { label: "历史 CVAT 待初始化", group: "pending" };
    }
    if (record.unresolved_issue_count > 0) {
      return { label: "存在问题", group: "problem" };
    }
    if (record.cvat_status_summary.validation || record.cvat_status_summary.review) {
      return { label: "待复核", group: "review" };
    }
    if (record.cvat_status_summary.completed || record.cvat_status_summary.done || record.cvat_status_summary.finished) {
      return { label: "已完成", group: "completed" };
    }
    if (record.initialized_video_count > 0) {
      return { label: "标注中", group: "in_progress" };
    }
    return { label: "待处理", group: "pending" };
  }
  if (record.video_count > 0 && record.initialized_video_count === 0) {
    return { label: "原生待标注", group: "pending" };
  }
  return { label: "原生标注中", group: "in_progress" };
}

function normalizeImageTask(record: AnnotationTaskListItem): UnifiedTaskItem {
  const status = normalizeImageStatus(record.status);
  return {
    id: record.task_id,
    name: record.task_name,
    dataType: "image",
    taskType: record.task_type,
    datasetName: record.dataset_name || record.dataset_id,
    itemCount: record.image_count,
    annotationBackend: "label_studio",
    toolLabel: "Label Studio",
    status: record.status,
    statusLabel: status.label,
    statusGroup: status.group,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    detailPath: `/tasks/${record.task_id}`,
  };
}

function normalizeVideoTask(record: VideoDatasetListItem): UnifiedTaskItem {
  const status = normalizeVideoStatus(record);
  const legacy = record.annotation_backend === "label_studio";
  const cvat = record.annotation_backend === "cvat";
  return {
    id: record.dataset_id,
    name: record.dataset_name,
    dataType: "video",
    taskType: record.task_type,
    datasetName: record.dataset_name,
    itemCount: record.video_count,
    annotationBackend: legacy ? "label_studio" : cvat ? "cvat" : "native_video",
    toolLabel: legacy ? "Label Studio 旧版" : cvat ? "CVAT 历史兼容" : "原生视频工作台",
    status: JSON.stringify(record.cvat_status_summary || {}),
    statusLabel: status.label,
    statusGroup: status.group,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    detailPath: `/tasks/video/${record.dataset_id}`,
    legacy,
  };
}

function compareTasks(a: UnifiedTaskItem, b: UnifiedTaskItem, sortMode: SortMode) {
  if (sortMode === "name_asc") {
    return a.name.localeCompare(b.name, "zh-CN") || a.id.localeCompare(b.id);
  }
  const aUpdated = sortTime(a.updatedAt || a.createdAt);
  const bUpdated = sortTime(b.updatedAt || b.createdAt);
  const aCreated = sortTime(a.createdAt);
  const bCreated = sortTime(b.createdAt);
  if (sortMode === "updated_asc") {
    return aUpdated - bUpdated || a.name.localeCompare(b.name, "zh-CN") || a.id.localeCompare(b.id);
  }
  if (sortMode === "created_desc") {
    return bCreated - aCreated || a.name.localeCompare(b.name, "zh-CN") || a.id.localeCompare(b.id);
  }
  return bUpdated - aUpdated || a.name.localeCompare(b.name, "zh-CN") || a.id.localeCompare(b.id);
}

export function TaskListPage() {
  const navigate = useNavigate();
  const [imageTasks, setImageTasks] = useState<AnnotationTaskListItem[]>([]);
  const [videoTasks, setVideoTasks] = useState<VideoDatasetListItem[]>([]);
  const [imageTotal, setImageTotal] = useState(0);
  const [videoTotal, setVideoTotal] = useState(0);
  const [loadingImages, setLoadingImages] = useState(true);
  const [loadingVideos, setLoadingVideos] = useState(true);
  const [imageError, setImageError] = useState<string | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const [dataTypeFilter, setDataTypeFilter] = useState<DataTypeFilter>("all");
  const [taskTypeFilter, setTaskTypeFilter] = useState<TaskType | "all">("all");
  const [statusFilter, setStatusFilter] = useState<StatusGroup>("all");
  const [toolFilter, setToolFilter] = useState<ToolFilter>("all");
  const [sortMode, setSortMode] = useState<SortMode>("updated_desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const resetPage = () => setPage(1);

  const loadImageTasks = useCallback(async () => {
    try {
      setLoadingImages(true);
      setImageError(null);
      const response = await listTasks();
      setImageTasks(response.items);
      setImageTotal(response.total);
    } catch (error) {
      setImageTasks([]);
      setImageTotal(0);
      setImageError(error instanceof Error ? error.message : "图片任务加载失败，请刷新重试。");
    } finally {
      setLoadingImages(false);
    }
  }, []);

  const loadVideoTasks = useCallback(async () => {
    try {
      setLoadingVideos(true);
      setVideoError(null);
      const response = await listVideoDatasets();
      setVideoTasks(response.items);
      setVideoTotal(response.total);
    } catch (error) {
      setVideoTasks([]);
      setVideoTotal(0);
      setVideoError(error instanceof Error ? error.message : "视频任务加载失败，请刷新重试。");
    } finally {
      setLoadingVideos(false);
    }
  }, []);

  const reloadAll = useCallback(() => {
    void loadImageTasks();
    void loadVideoTasks();
  }, [loadImageTasks, loadVideoTasks]);

  useEffect(() => {
    reloadAll();
  }, [reloadAll]);

  const unifiedTasks = useMemo(
    () => [...imageTasks.map(normalizeImageTask), ...videoTasks.map(normalizeVideoTask)],
    [imageTasks, videoTasks],
  );

  const filteredTasks = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    return unifiedTasks
      .filter((item) => {
        if (!normalizedKeyword) {
          return true;
        }
        return [item.name, item.datasetName, item.id].some((value) => value.toLowerCase().includes(normalizedKeyword));
      })
      .filter((item) => dataTypeFilter === "all" || item.dataType === dataTypeFilter)
      .filter((item) => taskTypeFilter === "all" || item.taskType === taskTypeFilter)
      .filter((item) => statusFilter === "all" || item.statusGroup === statusFilter)
      .filter((item) => {
        if (toolFilter === "all") {
          return true;
        }
        if (toolFilter === "label_studio_legacy") {
          return item.legacy === true;
        }
        return item.annotationBackend === toolFilter && !item.legacy;
      })
      .sort((a, b) => compareTasks(a, b, sortMode));
  }, [dataTypeFilter, keyword, sortMode, statusFilter, taskTypeFilter, toolFilter, unifiedTasks]);

  const clearFilters = () => {
    setKeyword("");
    setDataTypeFilter("all");
    setTaskTypeFilter("all");
    setStatusFilter("all");
    setToolFilter("all");
    setSortMode("updated_desc");
    setPage(1);
  };

  const taskColumns = useMemo<ColumnsType<UnifiedTaskItem>>(
    () => [
      {
        title: "任务名称",
        dataIndex: "name",
        key: "name",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{record.name}</Typography.Text>
            <Typography.Text type="secondary">{record.id}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "数据类型",
        dataIndex: "dataType",
        key: "dataType",
        render: (value: UnifiedTaskItem["dataType"]) => <Tag color={value === "image" ? "green" : "blue"}>{value === "image" ? "图片" : "视频"}</Tag>,
      },
      {
        title: "任务类型",
        dataIndex: "taskType",
        key: "taskType",
        render: (value: TaskType) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{taskTypeLabels[value]}</Typography.Text>
            <Typography.Text type="secondary">{value}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "数据集",
        dataIndex: "datasetName",
        key: "datasetName",
      },
      {
        title: "数据量",
        key: "itemCount",
        render: (_, record) => `${record.itemCount} ${record.dataType === "image" ? "张图片" : "条视频"}`,
      },
      {
        title: "标注工具",
        key: "tool",
        render: (_, record) => <Tag color={record.annotationBackend === "cvat" ? "processing" : record.legacy ? "warning" : "default"}>{record.toolLabel}</Tag>,
      },
      {
        title: "状态",
        key: "status",
        render: (_, record) => <Tag color={record.statusGroup === "completed" ? "success" : record.statusGroup === "problem" ? "error" : record.statusGroup === "review" ? "warning" : "processing"}>{record.statusLabel}</Tag>,
      },
      {
        title: "更新时间",
        key: "updatedAt",
        render: (_, record) => (
          <Tooltip title={`created_at: ${record.createdAt || "-"}\nupdated_at: ${record.updatedAt || "-"}`}>
            <span>{formatDateTime(record.updatedAt || record.createdAt)}</span>
          </Tooltip>
        ),
      },
      {
        title: "操作",
        key: "actions",
        render: (_, record) => (
          <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => navigate(record.detailPath)}>
            进入任务详情
          </Button>
        ),
      },
    ],
    [navigate],
  );

  const loading = loadingImages || loadingVideos;
  const totalCount = imageTotal + videoTotal;
  const bothFailed = Boolean(imageError && videoError);

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Title level={2} className="detail-title">
            任务列表
          </Typography.Title>
          <Typography.Paragraph className="hero-description">
            图片任务使用 Label Studio 完成标注；新视频任务使用平台原生视频工作台，历史 CVAT 视频任务保留兼容入口。
          </Typography.Paragraph>
          <Space wrap>
            <Typography.Text>{loading ? "任务总数：加载中" : `任务总数：${totalCount}`}</Typography.Text>
            <Tag color="green">{`图片：${imageTotal}`}</Tag>
            <Tag color="blue">{`视频：${videoTotal}`}</Tag>
            <Typography.Text type="secondary">{loading ? "当前显示：加载中" : `当前显示：${filteredTasks.length}`}</Typography.Text>
            <Button icon={<ReloadOutlined />} onClick={reloadAll} loading={loading}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/")}>
              去创建任务
            </Button>
          </Space>
        </Space>
      </Card>

      <Card title="全部任务" className="panel-card task-list-card">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          {imageError ? <Alert type="warning" showIcon message="图片任务加载失败，请刷新重试。" description={imageError} /> : null}
          {videoError ? <Alert type="warning" showIcon message="视频任务加载失败，请刷新重试。" description={videoError} /> : null}
          <Space wrap>
            <Input.Search
              allowClear
              placeholder="搜索任务名称或数据集"
              style={{ width: 260 }}
              value={keyword}
              onChange={(event) => {
                setKeyword(event.target.value);
                resetPage();
              }}
            />
            <Select
              value={dataTypeFilter}
              style={{ width: 120 }}
              options={[
                { label: "全部", value: "all" },
                { label: "图片", value: "image" },
                { label: "视频", value: "video" },
              ]}
              onChange={(value) => {
                setDataTypeFilter(value);
                resetPage();
              }}
            />
            <Select
              value={taskTypeFilter}
              style={{ width: 170 }}
              options={[
                { label: "全部任务类型", value: "all" },
                { label: "目标框标注", value: "bbox" },
                { label: "多边形分割", value: "polygon" },
                { label: "目标框 + 多边形", value: "bbox_polygon" },
                { label: "B-line 视频分割", value: "video_bline_segmentation" },
              ]}
              onChange={(value) => {
                setTaskTypeFilter(value);
                resetPage();
              }}
            />
            <Select
              value={statusFilter}
              style={{ width: 140 }}
              options={[
                { label: "全部状态", value: "all" },
                { label: "待处理", value: "pending" },
                { label: "标注中", value: "in_progress" },
                { label: "待复核", value: "review" },
                { label: "已完成", value: "completed" },
                { label: "存在问题", value: "problem" },
                { label: "服务不可用", value: "unavailable" },
              ]}
              onChange={(value) => {
                setStatusFilter(value);
                resetPage();
              }}
            />
            <Select
              value={toolFilter}
              style={{ width: 160 }}
              options={[
                { label: "全部工具", value: "all" },
                { label: "Label Studio", value: "label_studio" },
                { label: "原生视频工作台", value: "native_video" },
                { label: "CVAT 历史兼容", value: "cvat" },
                { label: "Label Studio 旧版", value: "label_studio_legacy" },
              ]}
              onChange={(value) => {
                setToolFilter(value);
                resetPage();
              }}
            />
            <Select
              value={sortMode}
              style={{ width: 140 }}
              options={[
                { label: "最近更新", value: "updated_desc" },
                { label: "最早更新", value: "updated_asc" },
                { label: "最近创建", value: "created_desc" },
                { label: "任务名称 A-Z", value: "name_asc" },
              ]}
              onChange={(value) => {
                setSortMode(value);
                resetPage();
              }}
            />
            <Button onClick={clearFilters}>重置筛选</Button>
          </Space>

          {bothFailed ? (
            <Empty description="任务列表加载失败，请刷新重试。" image={Empty.PRESENTED_IMAGE_SIMPLE}>
              <Button icon={<ReloadOutlined />} onClick={reloadAll}>
                刷新
              </Button>
            </Empty>
          ) : filteredTasks.length === 0 && !loading ? (
            <Empty description="没有符合当前筛选条件的任务。" image={Empty.PRESENTED_IMAGE_SIMPLE}>
              <Button onClick={clearFilters}>清除筛选</Button>
            </Empty>
          ) : (
            <Table
              rowKey={(record) => `${record.dataType}:${record.id}`}
              loading={loading}
              columns={taskColumns}
              dataSource={filteredTasks}
              pagination={{
                current: page,
                pageSize,
                total: filteredTasks.length,
                showSizeChanger: true,
                pageSizeOptions: [10, 20, 50],
                showTotal: (total, range) => `共 ${total} 个任务，第 ${range[0]}-${range[1]} 条`,
                onChange: (nextPage, nextPageSize) => {
                  setPage(nextPage);
                  setPageSize(nextPageSize);
                },
              }}
              scroll={{ x: 1220 }}
            />
          )}
        </Space>
      </Card>
    </Space>
  );
}
