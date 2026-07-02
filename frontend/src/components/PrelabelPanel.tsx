import { Alert, Button, Card, Progress, Select, Space, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { listModels } from "../api/models";
import { getPrelabelJob, runPrelabel } from "../api/prelabel";
import type { ModelInfo, PrelabelJobStatusResponse, TaskType } from "../types/api";
import { StatusTag } from "./StatusTag";

interface PrelabelPanelProps {
  taskId: string;
  taskType: TaskType;
  detModelId?: string | null;
  segModelId?: string | null;
  onCompleted?: () => Promise<void> | void;
}

const fallbackModels: ModelInfo[] = [
  {
    model_id: "mock_detection",
    model_name: "Mock Detection Model",
    model_type: "detection",
    model_version: "mock-v1",
    status: "available",
    description: "本地 mock 检测模型，用于演示 bbox 预标注流程。",
  },
  {
    model_id: "mock_segmentation",
    model_name: "Mock Segmentation Model",
    model_type: "segmentation",
    model_version: "mock-v1",
    status: "available",
    description: "本地 mock 分割模型，用于演示 polygon 预标注流程。",
  },
];

const statusText: Record<string, string> = {
  available: "可用",
  not_configured: "未配置",
};

export function PrelabelPanel({
  taskId,
  taskType,
  detModelId,
  segModelId,
  onCompleted,
}: PrelabelPanelProps) {
  const [job, setJob] = useState<PrelabelJobStatusResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>(fallbackModels);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [selectedDetectionModelId, setSelectedDetectionModelId] = useState(detModelId || "mock_detection");
  const [selectedSegmentationModelId, setSelectedSegmentationModelId] = useState(segModelId || "mock_segmentation");

  useEffect(() => {
    setSelectedDetectionModelId(detModelId || "mock_detection");
  }, [detModelId]);

  useEffect(() => {
    setSelectedSegmentationModelId(segModelId || "mock_segmentation");
  }, [segModelId]);

  useEffect(() => {
    let active = true;

    async function loadModels() {
      try {
        const response = await listModels();
        if (!active) {
          return;
        }
        setModels(response.items);
        setModelsError(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setModels(fallbackModels);
        setModelsError(error instanceof Error ? error.message : "加载模型列表失败。");
      }
    }

    void loadModels();

    return () => {
      active = false;
    };
  }, []);

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

  const detectionModels = useMemo(
    () => models.filter((model) => model.model_type === "detection"),
    [models],
  );
  const segmentationModels = useMemo(
    () => models.filter((model) => model.model_type === "segmentation"),
    [models],
  );

  const selectedDetectionModel = detectionModels.find((model) => model.model_id === selectedDetectionModelId) || null;
  const selectedSegmentationModel =
    segmentationModels.find((model) => model.model_id === selectedSegmentationModelId) || null;

  const handleRunPrelabel = async () => {
    try {
      setSubmitting(true);
      const result = await runPrelabel(taskId, {
        detection_model_id:
          taskType === "bbox" || taskType === "bbox_polygon" ? selectedDetectionModelId : undefined,
        segmentation_model_id:
          taskType === "polygon" || taskType === "bbox_polygon" ? selectedSegmentationModelId : undefined,
      });
      const nextJob = await getPrelabelJob(result.job_id);
      setJob(nextJob);
      await onCompleted?.();
      message.success("AI 预标注已完成，可以前往 Label Studio 进行人工审核。");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "触发 AI 预标注失败。");
    } finally {
      setSubmitting(false);
    }
  };

  const progressPercent = job && job.total_count > 0 ? Math.round((job.success_count / job.total_count) * 100) : 0;

  return (
    <Card title="AI 预标注" extra={<StatusTag status={job?.status || "created"} />} className="panel-card">
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Typography.Paragraph className="muted-paragraph">
          这里会调用后端的模型服务，为当前任务写入 bbox / polygon 预标注。当前默认仍使用 mock 模型，后续可以按统一契约切换到真实模型实现。
        </Typography.Paragraph>

        {modelsError ? <Alert type="warning" showIcon message={modelsError} /> : null}
        {job?.error_message ? <Alert type="warning" showIcon message={job.error_message} /> : null}

        {taskType === "bbox" || taskType === "bbox_polygon" ? (
          <div>
            <Typography.Text strong>检测模型</Typography.Text>
            <Select
              style={{ width: "100%", marginTop: 8 }}
              value={selectedDetectionModelId}
              onChange={setSelectedDetectionModelId}
              options={detectionModels.map((model) => ({
                value: model.model_id,
                label: `${model.model_name} (${statusText[model.status] || model.status})`,
              }))}
            />
            {selectedDetectionModel ? (
              <Typography.Paragraph className="muted-paragraph" style={{ marginTop: 8 }}>
                {selectedDetectionModel.description}
              </Typography.Paragraph>
            ) : null}
          </div>
        ) : null}

        {taskType === "polygon" || taskType === "bbox_polygon" ? (
          <div>
            <Typography.Text strong>分割模型</Typography.Text>
            <Select
              style={{ width: "100%", marginTop: 8 }}
              value={selectedSegmentationModelId}
              onChange={setSelectedSegmentationModelId}
              options={segmentationModels.map((model) => ({
                value: model.model_id,
                label: `${model.model_name} (${statusText[model.status] || model.status})`,
              }))}
            />
            {selectedSegmentationModel ? (
              <Typography.Paragraph className="muted-paragraph" style={{ marginTop: 8 }}>
                {selectedSegmentationModel.description}
              </Typography.Paragraph>
            ) : null}
          </div>
        ) : null}

        {selectedDetectionModel?.status === "not_configured" || selectedSegmentationModel?.status === "not_configured" ? (
          <Alert
            type="info"
            showIcon
            message="你当前选择了“未配置”模型。触发预标注时，后端会给出明确提示，方便后续替换为真实模型实现。"
          />
        ) : null}

        {job ? <Progress percent={progressPercent} status={job.status === "failed" ? "exception" : "active"} /> : null}

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
