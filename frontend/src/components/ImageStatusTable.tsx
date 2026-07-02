import React from "react";
import { Button, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { TaskImageStatusItem } from "../types/api";
import { StatusTag } from "./StatusTag";

interface ImageStatusTableProps {
  images: TaskImageStatusItem[];
  loading?: boolean;
  onEnterLabel?: (image: TaskImageStatusItem) => void;
  onPreviewPrediction?: (image: TaskImageStatusItem) => void;
}

function renderPredictionStatus(status?: string) {
  if (status === "written") {
    return <Tag color="success">已写入</Tag>;
  }
  if (status === "failed") {
    return <Tag color="error">失败</Tag>;
  }
  return <Tag color="default">未生成</Tag>;
}

function renderAnnotationStatus(status?: string) {
  if (status === "saved") {
    return <Tag color="success">已保存</Tag>;
  }
  return <Tag color="default">未保存</Tag>;
}

export function ImageStatusTable({ images, loading, onEnterLabel, onPreviewPrediction }: ImageStatusTableProps) {
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
      dataIndex: "prediction_status",
      key: "prediction_status",
      render: (value: string | undefined) => renderPredictionStatus(value),
    },
    {
      title: "人工 Annotation",
      dataIndex: "annotation_status",
      key: "annotation_status",
      render: (value: string | undefined) => renderAnnotationStatus(value),
    },
    {
      title: "操作",
      key: "actions",
      render: (_, image) => {
        const previewDisabled = !(image.prediction_status === "written" || image.has_prediction);
        const labelDisabled = !image.label_studio_task_url;

        return (
          <Space direction="vertical" size={4}>
            <Space wrap>
              <Tooltip title={previewDisabled ? "当前图像暂无 AI prediction，可先触发预标注并同步状态。" : ""}>
                <Button type="link" disabled={previewDisabled} onClick={() => onPreviewPrediction?.(image)}>
                  预览 AI 结果
                </Button>
              </Tooltip>
              <Tooltip title={labelDisabled ? "暂无 task URL，请先同步或重新创建任务" : ""}>
                <Button type="link" disabled={labelDisabled} onClick={() => onEnterLabel?.(image)}>
                  进入标注
                </Button>
              </Tooltip>
            </Space>
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
      scroll={{ x: 980 }}
    />
  );
}
