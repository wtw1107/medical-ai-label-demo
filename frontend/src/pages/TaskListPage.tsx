import React from "react";
import { ExportOutlined, FolderOpenOutlined, InfoCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, Space, Table, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listTasks } from "../api/tasks";
import { listVideoDatasets } from "../api/videos";
import { StatusTag } from "../components/StatusTag";
import type { AnnotationTaskListItem, VideoDatasetListItem } from "../types/api";

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function TaskListPage() {
  const navigate = useNavigate();
  const [imageTasks, setImageTasks] = useState<AnnotationTaskListItem[]>([]);
  const [videoTasks, setVideoTasks] = useState<VideoDatasetListItem[]>([]);
  const [loadingImages, setLoadingImages] = useState(true);
  const [loadingVideos, setLoadingVideos] = useState(true);

  useEffect(() => {
    let active = true;

    async function loadImageTasks() {
      try {
        setLoadingImages(true);
        const response = await listTasks();
        if (active) {
          setImageTasks(response.items);
        }
      } catch (error) {
        if (active) {
          setImageTasks([]);
          message.error(error instanceof Error ? error.message : "加载图片任务列表失败。");
        }
      } finally {
        if (active) {
          setLoadingImages(false);
        }
      }
    }

    async function loadVideoTasks() {
      try {
        setLoadingVideos(true);
        const response = await listVideoDatasets();
        if (active) {
          setVideoTasks(response.items);
        }
      } catch (error) {
        if (active) {
          setVideoTasks([]);
          message.error(error instanceof Error ? error.message : "加载视频任务列表失败。");
        }
      } finally {
        if (active) {
          setLoadingVideos(false);
        }
      }
    }

    void loadImageTasks();
    void loadVideoTasks();

    return () => {
      active = false;
    };
  }, []);

  const imageColumns = useMemo<ColumnsType<AnnotationTaskListItem>>(
    () => [
      {
        title: "任务名称",
        dataIndex: "task_name",
        key: "task_name",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{record.task_name}</Typography.Text>
            <Typography.Text type="secondary">{record.task_id}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "任务类型",
        dataIndex: "task_type",
        key: "task_type",
      },
      {
        title: "数据集",
        key: "dataset",
        render: (_, record) => record.dataset_name || record.dataset_id,
      },
      {
        title: "图片数量",
        dataIndex: "image_count",
        key: "image_count",
      },
      {
        title: "AI 已预标注",
        dataIndex: "prediction_written_count",
        key: "prediction_written_count",
      },
      {
        title: (
          <Space size={4}>
            <span>人工已保存</span>
            <Tooltip title="任务列表不强制实时同步 Label Studio，请进入任务详情页同步后查看准确状态。">
              <InfoCircleOutlined />
            </Tooltip>
          </Space>
        ),
        dataIndex: "annotation_saved_count",
        key: "annotation_saved_count",
        render: () => "-",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        render: (value: string) => <StatusTag status={value} />,
      },
      {
        title: "更新时间",
        dataIndex: "updated_at",
        key: "updated_at",
        render: (value: string) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        render: (_, record) => (
          <Space wrap>
            <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => navigate(`/tasks/${record.task_id}`)}>
              进入任务详情
            </Button>
            <Button
              icon={<ExportOutlined />}
              disabled={!record.label_studio_project_url}
              onClick={() => {
                if (!record.label_studio_project_url) {
                  message.warning("当前任务还没有可用的 Label Studio 链接。");
                  return;
                }
                window.open(record.label_studio_project_url, "_blank", "noopener,noreferrer");
              }}
            >
              打开 Label Studio
            </Button>
          </Space>
        ),
      },
    ],
    [navigate],
  );

  const videoColumns = useMemo<ColumnsType<VideoDatasetListItem>>(
    () => [
      {
        title: "任务名称",
        dataIndex: "dataset_name",
        key: "dataset_name",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{record.dataset_name}</Typography.Text>
            <Typography.Text type="secondary">{record.dataset_id}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "任务类型",
        dataIndex: "task_type",
        key: "task_type",
        render: () => "肺超声 B-line 视频关键帧分割",
      },
      {
        title: "患者数",
        dataIndex: "patient_count",
        key: "patient_count",
      },
      {
        title: "视频数",
        dataIndex: "video_count",
        key: "video_count",
      },
      {
        title: "关键帧",
        dataIndex: "keyframe_count",
        key: "keyframe_count",
      },
      {
        title: "已标注关键帧",
        dataIndex: "annotated_count",
        key: "annotated_count",
      },
      {
        title: "已审核视频",
        dataIndex: "reviewed_count",
        key: "reviewed_count",
      },
      {
        title: "更新时间",
        dataIndex: "updated_at",
        key: "updated_at",
        render: (value: string) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        render: (_, record) => (
          <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => navigate(`/tasks/video/${record.dataset_id}`)}>
            进入任务详情
          </Button>
        ),
      },
    ],
    [navigate],
  );

  const totalCount = imageTasks.length + videoTasks.length;

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Title level={2} className="detail-title">
            任务列表
          </Typography.Title>
          <Typography.Paragraph className="hero-description">
            这里集中查看图片标注任务与肺超声 B-line 视频关键帧分割任务。图片任务仍走原 AI 预标注与 Label Studio 流程，视频任务走视频审核、关键帧标注与 B-line mask 导出流程。
          </Typography.Paragraph>
          <Space wrap>
            <Typography.Text>任务总数：{totalCount}</Typography.Text>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/")}>
              去创建任务
            </Button>
          </Space>
        </Space>
      </Card>

      <Alert
        type="info"
        showIcon
        message="图片任务与视频任务暂时使用各自稳定的数据模型，当前页面先做统一入口和统一浏览。"
      />

      <Card title="图片任务" className="panel-card task-list-card">
        {imageTasks.length === 0 && !loadingImages ? (
          <Empty description="暂无图片任务，请先上传图片并创建标注任务。" image={Empty.PRESENTED_IMAGE_SIMPLE}>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/")}>
              去创建任务
            </Button>
          </Empty>
        ) : (
          <Table
            rowKey="task_id"
            loading={loadingImages}
            columns={imageColumns}
            dataSource={imageTasks}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            scroll={{ x: 1080 }}
          />
        )}
      </Card>

      <Card title="视频任务" className="panel-card task-list-card">
        {videoTasks.length === 0 && !loadingVideos ? (
          <Empty description="暂无视频任务，请先从统一上传入口上传视频数据集。" image={Empty.PRESENTED_IMAGE_SIMPLE}>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/")}>
              去创建任务
            </Button>
          </Empty>
        ) : (
          <Table
            rowKey="dataset_id"
            loading={loadingVideos}
            columns={videoColumns}
            dataSource={videoTasks}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            scroll={{ x: 1080 }}
          />
        )}
      </Card>
    </Space>
  );
}
