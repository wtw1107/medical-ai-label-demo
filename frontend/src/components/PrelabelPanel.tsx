import { Alert, Button, Card, Progress, Space, Typography, message } from "antd";
import { useEffect, useState } from "react";

import { getPrelabelJob, runPrelabel } from "../api/prelabel";
import type { PrelabelJobStatusResponse } from "../types/api";
import { StatusTag } from "./StatusTag";

interface PrelabelPanelProps {
  taskId: string;
  onCompleted?: () => Promise<void> | void;
}

export function PrelabelPanel({ taskId, onCompleted }: PrelabelPanelProps) {
  const [job, setJob] = useState<PrelabelJobStatusResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!job || !["running", "pending"].includes(job.status)) {
      return undefined;
    }

    const timer = window.setInterval(async () => {
      const next = await getPrelabelJob(job.job_id);
      setJob(next);
      if (["completed", "failed", "partial_failed"].includes(next.status)) {
        window.clearInterval(timer);
        await onCompleted?.();
      }
    }, 2500);

    return () => window.clearInterval(timer);
  }, [job, onCompleted]);

  const handleRunPrelabel = async () => {
    try {
      setSubmitting(true);
      const result = await runPrelabel(taskId);
      const nextJob = await getPrelabelJob(result.job_id);
      setJob(nextJob);
      await onCompleted?.();
      message.success("AI 预标注已完成，可前往 Label Studio 进行人工审核。");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "触发 AI 预标注失败");
    } finally {
      setSubmitting(false);
    }
  };

  const progressPercent = job && job.total_count > 0 ? Math.round((job.success_count / job.total_count) * 100) : 0;

  return (
    <Card
      title="AI 预标注"
      extra={<StatusTag status={job?.status || "created"} />}
      className="panel-card"
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Typography.Paragraph className="muted-paragraph">
          这里会调用后端的 Mock 模型服务，为当前任务写入 bbox / polygon 预标注，之后仍需在 Label Studio 中完成人工确认。
        </Typography.Paragraph>
        {job?.error_message ? <Alert type="warning" showIcon message={job.error_message} /> : null}
        {job ? (
          <Progress percent={progressPercent} status={job.status === "failed" ? "exception" : "active"} />
        ) : null}
        {job ? (
          <Space wrap size={16}>
            <Typography.Text>总数：{job.total_count}</Typography.Text>
            <Typography.Text>成功：{job.success_count}</Typography.Text>
            <Typography.Text>失败：{job.failed_count}</Typography.Text>
          </Space>
        ) : null}
        <Button type="primary" size="large" loading={submitting} onClick={handleRunPrelabel}>
          触发 AI 预标注
        </Button>
      </Space>
    </Card>
  );
}
