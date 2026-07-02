import { Tag } from "antd";

const statusColorMap: Record<string, string> = {
  uploaded: "default",
  ready: "processing",
  created: "default",
  prelabeling: "processing",
  prelabel_done: "success",
  prelabel_failed: "error",
  reviewing: "gold",
  confirmed: "success",
  completed: "success",
  running: "processing",
  failed: "error",
  partial_failed: "warning",
  exported: "success",
  error: "error",
};

const statusTextMap: Record<string, string> = {
  uploaded: "已上传",
  ready: "可用",
  created: "已创建",
  prelabeling: "预标注中",
  prelabel_done: "预标注完成",
  prelabel_failed: "预标注失败",
  reviewing: "待人工确认",
  confirmed: "已人工确认",
  completed: "已完成",
  running: "进行中",
  failed: "失败",
  partial_failed: "部分失败",
  exported: "已导出",
  error: "异常",
};

export function StatusTag({ status }: { status: string }) {
  return <Tag color={statusColorMap[status] || "default"}>{statusTextMap[status] || status}</Tag>;
}
