import { Alert, Button, Card, Col, Form, Radio, Row, Space, Statistic, Typography, message } from "antd";
import { useMemo, useState } from "react";

import { createExport, getExportDownloadUrl, getExportStatus } from "../api/exports";
import type { ExportFormat, ExportStatusResponse, TaskImageStatusItem } from "../types/api";
import { StatusTag } from "./StatusTag";

interface ExportPanelProps {
  taskId: string;
  images: TaskImageStatusItem[];
  onExported?: () => Promise<void> | void;
}

const exportDescriptions: Record<ExportFormat, string> = {
  simple_json: "轻量结构化 JSON，便于快速查看和后处理。",
  label_studio_json: "保留 Label Studio 原始 annotation 结构。",
  mask_png: "将 polygon 结果转换为二值 mask PNG 并打包。",
};

export function ExportPanel({ taskId, images, onExported }: ExportPanelProps) {
  const [form] = Form.useForm<{ format: ExportFormat }>();
  const [exportStatus, setExportStatus] = useState<ExportStatusResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const selectedFormat = Form.useWatch("format", form) || "simple_json";

  const exportSummary = useMemo(() => {
    const total = images.length;
    const predicted = images.filter((image) => image.prediction_status === "written").length;
    const saved = images.filter((image) => image.annotation_status === "saved").length;
    return { total, predicted, saved };
  }, [images]);

  const handleCreateExport = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const created = await createExport(taskId, {
        format: values.format,
        range: "confirmed_only",
      });
      const latestStatus = await getExportStatus(created.export_id);
      setExportStatus(latestStatus);
      await onExported?.();
      message.success("导出文件已生成，可以直接下载 ZIP。");
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card title="导出结果" extra={<StatusTag status={exportStatus?.status || "created"} />} className="panel-card">
      <Space direction="vertical" size={20} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          message="导出前建议先同步 Label Studio 状态，确认人工 annotation 已保存。当前导出仍基于已保存 annotation，不会直接导出未确认 prediction。"
        />
        {exportStatus?.error_message ? <Alert type="warning" showIcon message={exportStatus.error_message} /> : null}

        <Form form={form} layout="vertical" initialValues={{ format: "simple_json" }}>
          <Form.Item label="导出格式" name="format">
            <Radio.Group optionType="button" buttonStyle="solid">
              <Radio.Button value="simple_json">simple_json</Radio.Button>
              <Radio.Button value="label_studio_json">label_studio_json</Radio.Button>
              <Radio.Button value="mask_png">mask_png</Radio.Button>
            </Radio.Group>
          </Form.Item>
        </Form>

        <Alert type="success" showIcon message={exportDescriptions[selectedFormat]} />

        <Card size="small" className="export-summary-card">
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Typography.Text strong>导出前摘要</Typography.Text>
            <Row gutter={[16, 16]}>
              <Col xs={24} sm={8}>
                <Statistic title="图像总数" value={exportSummary.total} />
              </Col>
              <Col xs={24} sm={8}>
                <Statistic title="AI 已预标注" value={exportSummary.predicted} />
              </Col>
              <Col xs={24} sm={8}>
                <Statistic title="人工已保存" value={exportSummary.saved} />
              </Col>
            </Row>
            <Typography.Text type="secondary">当前导出范围：仅已保存 annotation。</Typography.Text>
            <Typography.Text type="secondary">当前格式：{selectedFormat}</Typography.Text>
          </Space>
        </Card>

        <Space wrap>
          <Button type="primary" size="large" loading={submitting} onClick={handleCreateExport}>
            创建导出任务
          </Button>
          {exportStatus?.export_id ? (
            <Button href={getExportDownloadUrl(exportStatus.export_id)} target="_blank">
              下载导出 ZIP
            </Button>
          ) : null}
        </Space>

        {exportStatus ? (
          <Alert
            type="info"
            showIcon
            message={`导出状态：${exportStatus.status}`}
            description={`已导出确认图像数：${exportStatus.total_count}`}
          />
        ) : null}
      </Space>
    </Card>
  );
}
