import { ExportOutlined, FolderOpenOutlined, InfoCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, Space, Table, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { listTasks } from "../api/tasks";
import { StatusTag } from "../components/StatusTag";
import type { AnnotationTaskListItem } from "../types/api";

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
  const [tasks, setTasks] = useState<AnnotationTaskListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function loadTasks() {
      try {
        setLoading(true);
        const response = await listTasks();
        if (!active) {
          return;
        }
        setTasks(response.items);
      } catch (error) {
        if (!active) {
          return;
        }
        setTasks([]);
        message.error(error instanceof Error ? error.message : "加载任务列表失败。");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadTasks();

    return () => {
      active = false;
    };
  }, []);

  const columns = useMemo<ColumnsType<AnnotationTaskListItem>>(
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
        render: () => "—",
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

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Title level={2} className="detail-title">
            任务列表
          </Typography.Title>
          <Typography.Paragraph className="hero-description">
            这里集中查看已经创建的 AI 辅助标注任务。你可以重新进入任务详情，继续预标注、同步状态、查看只读 AI
            预览、打开 Label Studio 或执行导出。
          </Typography.Paragraph>
          <Space wrap>
            <Typography.Text>任务总数：{tasks.length}</Typography.Text>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/")}>
              去创建任务
            </Button>
          </Space>
        </Space>
      </Card>

      <Alert
        type="info"
        showIcon
        message="任务列表统计不强制实时同步 Label Studio。若需要查看准确的人工保存状态，请进入任务详情页后点击“同步 Label Studio 状态”。"
      />

      <Card title="已有任务" className="panel-card task-list-card">
        {tasks.length === 0 && !loading ? (
          <Empty
            description="暂无任务，请先上传数据并创建标注任务。"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/")}>
              去创建任务
            </Button>
          </Empty>
        ) : (
          <Table
            rowKey="task_id"
            loading={loading}
            columns={columns}
            dataSource={tasks}
            pagination={{ pageSize: 8, showSizeChanger: false }}
            scroll={{ x: 1080 }}
          />
        )}
      </Card>
    </Space>
  );
}
