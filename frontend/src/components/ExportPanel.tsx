import { Alert, Button, Card, Form, Radio, Space, Typography, message } from "antd";
import { useState } from "react";

import { createExport, getExportDownloadUrl, getExportStatus } from "../api/exports";
import type { ExportFormat, ExportStatusResponse } from "../types/api";
import { StatusTag } from "./StatusTag";

interface ExportPanelProps {
  taskId: string;
  onExported?: () => Promise<void> | void;
}

export function ExportPanel({ taskId, onExported }: ExportPanelProps) {
  const [form] = Form.useForm<{ format: ExportFormat }>();
  const [exportStatus, setExportStatus] = useState<ExportStatusResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

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
      message.success("导出文件已生成，可以直接下载 zip。");
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
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Typography.Paragraph className="muted-paragraph">
          这里只导出人工保存后的 annotation，不会把未确认的 AI prediction 直接当作结果导出。
        </Typography.Paragraph>
        {exportStatus?.error_message ? <Alert type="warning" showIcon message={exportStatus.error_message} /> : null}
        <Form form={form} layout="vertical" initialValues={{ format: "simple_json" }}>
          <Form.Item label="导出格式" name="format">
            <Radio.Group optionType="button" buttonStyle="solid">
              <Radio.Button value="simple_json">简化 JSON</Radio.Button>
              <Radio.Button value="label_studio_json">Label Studio JSON</Radio.Button>
              <Radio.Button value="mask_png">Mask PNG</Radio.Button>
            </Radio.Group>
          </Form.Item>
        </Form>
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
            description={`已确认图像数：${exportStatus.total_count}`}
          />
        ) : null}
      </Space>
    </Card>
  );
}
