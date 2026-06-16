import { Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { TaskImageStatusItem } from "../types/api";
import { StatusTag } from "./StatusTag";

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
];

export function ImageStatusTable({ images, loading }: { images: TaskImageStatusItem[]; loading?: boolean }) {
  return (
    <Table<TaskImageStatusItem>
      rowKey="image_id"
      columns={columns}
      dataSource={images}
      loading={loading}
      pagination={false}
      scroll={{ x: 720 }}
    />
  );
}
