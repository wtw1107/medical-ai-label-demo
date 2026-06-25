import { Button, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { TaskImageStatusItem } from "../types/api";
import { StatusTag } from "./StatusTag";

interface ImageStatusTableProps {
  images: TaskImageStatusItem[];
  loading?: boolean;
  onEnterLabel?: (image: TaskImageStatusItem) => void;
}

export function ImageStatusTable({ images, loading, onEnterLabel }: ImageStatusTableProps) {
  const columns: ColumnsType<TaskImageStatusItem> = [
    {
      title: "文件名",
      dataIndex: "filename",
      key: "filename",
      render: (value: string) => <Typography.Text strong>{value}</Typography.Text>,
    },
    {
      title: "图像状态",
      dataIndex: "status",
      key: "status",
      render: (value: string) => <StatusTag status={value} />,
    },
    {
      title: "AI Prediction",
      dataIndex: "has_prediction",
      key: "has_prediction",
      render: (value: boolean) => <Tag color={value ? "success" : "default"}>{value ? "已写入" : "未写入"}</Tag>,
    },
    {
      title: "人工 Annotation",
      dataIndex: "has_annotation",
      key: "has_annotation",
      render: (value: boolean) => <Tag color={value ? "success" : "default"}>{value ? "已保存" : "未保存"}</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      render: (_, image) => {
        const disabled = !image.label_studio_task_url;
        const actionButton = (
          <Button type="link" disabled={disabled} onClick={() => onEnterLabel?.(image)}>
            进入标注
          </Button>
        );

        return (
          <Space direction="vertical" size={4}>
            {disabled ? <Tooltip title="暂无 task URL，请先同步或重新创建任务">{actionButton}</Tooltip> : actionButton}
            {image.label_studio_task_id ? (
              <Typography.Text type="secondary">Task #{image.label_studio_task_id}</Typography.Text>
            ) : (
              <Typography.Text type="secondary">未同步 task URL</Typography.Text>
            )}
          </Space>
        );
      },
    },
  ];

  return (
    <Table<TaskImageStatusItem>
      rowKey="image_id"
      columns={columns}
      dataSource={images}
      loading={loading}
      pagination={false}
      scroll={{ x: 880 }}
    />
  );
}
