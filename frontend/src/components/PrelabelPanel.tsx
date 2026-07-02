import React from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Divider,
  Drawer,
  Progress,
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
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
    description: "Local mock detection model for bbox prelabel demos.",
    deployment_type: "mock",
    provider: "local_demo",
    task_types: ["bbox", "bbox_polygon"],
    outputs: ["bbox", "confidence", "metadata"],
    limitations: ["Synthetic demo predictions", "Not a real AI model"],
  },
  {
    model_id: "mock_segmentation",
    model_name: "Mock Segmentation Model",
    model_type: "segmentation",
    model_version: "mock-v1",
    status: "available",
    description: "Local mock segmentation model for polygon prelabel demos.",
    deployment_type: "mock",
    provider: "local_demo",
    task_types: ["polygon", "bbox_polygon"],
    outputs: ["polygon", "metadata"],
    limitations: ["Synthetic demo polygons", "Not a real segmentation model"],
  },
];

const statusText: Record<string, string> = {
  available: "可用",
  not_configured: "未配置",
};

const deploymentText: Record<string, string> = {
  mock: "mock",
  external_api: "external_api",
  local_model_placeholder: "local_model_placeholder",
};

const statusColorMap: Record<string, string> = {
  available: "success",
  not_configured: "default",
  mock: "processing",
  external_api: "purple",
  local_model_placeholder: "gold",
};

function formatList(items?: string[] | null) {
  if (!items || items.length === 0) {
    return "未配置";
  }
  return items.join(" / ");
}

function ModelSummaryCard({
  model,
  onOpenDetails,
  highlighted,
}: {
  model: ModelInfo | null;
  onOpenDetails: () => void;
  highlighted?: boolean;
}) {
  return (
    <Card
      size="small"
      className="model-summary-card"
      title={model ? model.model_name : "未选择模型"}
      extra={
        model ? (
          <Space wrap>
            <Tag color={statusColorMap[model.status] || "default"}>{statusText[model.status] || model.status}</Tag>
            <Tag color={statusColorMap[model.deployment_type || ""] || "default"}>
              {deploymentText[model.deployment_type || ""] || model.deployment_type || "unknown"}
            </Tag>
          </Space>
        ) : null
      }
      bordered={highlighted}
    >
      {model ? (
        <Space direction="vertical" size={10} style={{ width: "100%" }}>
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="模型 ID">{model.model_id}</Descriptions.Item>
            <Descriptions.Item label="版本">{model.model_version}</Descriptions.Item>
            <Descriptions.Item label="Provider">{model.provider || "local_demo"}</Descriptions.Item>
            <Descriptions.Item label="任务类型">{formatList(model.task_types)}</Descriptions.Item>
            <Descriptions.Item label="输出类型">{formatList(model.outputs)}</Descriptions.Item>
          </Descriptions>
          <Space wrap>
            <Tag color="blue">{model.model_type}</Tag>
            {model.anatomy?.length ? <Tag color="cyan">{formatList(model.anatomy)}</Tag> : null}
            {model.modality?.length ? <Tag color="geekblue">{formatList(model.modality)}</Tag> : null}
          </Space>
          <Button block onClick={onOpenDetails}>
            查看模型详情
          </Button>
        </Space>
      ) : (
        <Typography.Text type="secondary">当前任务暂未配置可用模型。</Typography.Text>
      )}
    </Card>
  );
}

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
  const [activeModelId, setActiveModelId] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

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

  const detectionModels = useMemo(() => models.filter((model) => model.model_type === "detection"), [models]);
  const segmentationModels = useMemo(() => models.filter((model) => model.model_type === "segmentation"), [models]);

  const selectedDetectionModel = detectionModels.find((model) => model.model_id === selectedDetectionModelId) || null;
  const selectedSegmentationModel =
    segmentationModels.find((model) => model.model_id === selectedSegmentationModelId) || null;

  const activeModel = models.find((model) => model.model_id === activeModelId) || null;

  const handleOpenModelDetails = (modelId: string | null) => {
    if (!modelId) {
      return;
    }
    setActiveModelId(modelId);
    setDetailsOpen(true);
  };

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
    <>
      <Card
        title="AI 预标注"
        extra={<StatusTag status={job?.status || "created"} />}
        className="panel-card"
      >
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <Typography.Paragraph className="muted-paragraph">
            这里负责调用后端模型服务，为当前任务写入 bbox / polygon 预标注。当前页面增加了模型使用控制台，
            可以在触发前先查看模型摘要、适用范围、配置要求和最近验证结果。
          </Typography.Paragraph>

          {modelsError ? <Alert type="warning" showIcon message={modelsError} /> : null}
          {job?.error_message ? <Alert type="warning" showIcon message={job.error_message} /> : null}
          <Alert
            type="info"
            showIcon
            message="如果模型对某张图返回 0 detections，不会写入空 prediction，也不会导致整个任务失败。"
          />

          <div className="model-console-grid">
            {(taskType === "bbox" || taskType === "bbox_polygon") ? (
              <ModelSummaryCard
                model={selectedDetectionModel}
                onOpenDetails={() => handleOpenModelDetails(selectedDetectionModelId)}
                highlighted
              />
            ) : null}

            {(taskType === "polygon" || taskType === "bbox_polygon") ? (
              <ModelSummaryCard
                model={selectedSegmentationModel}
                onOpenDetails={() => handleOpenModelDetails(selectedSegmentationModelId)}
                highlighted
              />
            ) : null}
          </div>

          {(taskType === "bbox" || taskType === "bbox_polygon") ? (
            <div className="model-control-block">
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
              <Button type="link" onClick={() => handleOpenModelDetails(selectedDetectionModelId)} style={{ padding: 0 }}>
                查看检测模型详情
              </Button>
            </div>
          ) : null}

          {(taskType === "polygon" || taskType === "bbox_polygon") ? (
            <div className="model-control-block">
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
              <Button
                type="link"
                onClick={() => handleOpenModelDetails(selectedSegmentationModelId)}
                style={{ padding: 0 }}
              >
                查看分割模型详情
              </Button>
            </div>
          ) : null}

          {selectedDetectionModel?.status === "not_configured" || selectedSegmentationModel?.status === "not_configured" ? (
            <Alert
              type="info"
              showIcon
              message="你当前选择了“未配置”模型。触发预标注时，后端会给出清晰提示，方便后续替换为可用模型。"
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

      <Drawer
        title={activeModel ? `${activeModel.model_name} 模型详情` : "模型详情"}
        open={detailsOpen}
        width={760}
        onClose={() => setDetailsOpen(false)}
      >
        {activeModel ? (
          <Space direction="vertical" size={20} style={{ width: "100%" }}>
            <Alert
              type={activeModel.status === "available" ? "success" : "warning"}
              showIcon
              message={
                activeModel.deployment_type === "external_api"
                  ? "该模型通过 Roboflow 外部 API 调用。请确认当前数据允许发送到第三方服务。"
                  : activeModel.model_id === "mock_detection"
                    ? "该模型仅用于演示，不是真实 AI 预测。"
                    : activeModel.status === "not_configured"
                      ? "该模型尚未配置，当前不能用于预标注。"
                      : "该模型当前可用。"
              }
            />

            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="模型名称">{activeModel.model_name}</Descriptions.Item>
              <Descriptions.Item label="模型 ID">{activeModel.model_id}</Descriptions.Item>
              <Descriptions.Item label="版本">{activeModel.model_version}</Descriptions.Item>
              <Descriptions.Item label="模型类型">{activeModel.model_type}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColorMap[activeModel.status] || "default"}>
                  {statusText[activeModel.status] || activeModel.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="部署方式">
                <Tag color={statusColorMap[activeModel.deployment_type || ""] || "default"}>
                  {activeModel.deployment_type || "unknown"}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Provider">{activeModel.provider || "local_demo"}</Descriptions.Item>
              <Descriptions.Item label="适用任务">{formatList(activeModel.task_types)}</Descriptions.Item>
              <Descriptions.Item label="适用部位">{formatList(activeModel.anatomy)}</Descriptions.Item>
              <Descriptions.Item label="模态">{formatList(activeModel.modality)}</Descriptions.Item>
              <Descriptions.Item label="输出类型">{formatList(activeModel.outputs)}</Descriptions.Item>
              <Descriptions.Item label="API Key 需求">{activeModel.requires?.api_key ? "需要" : "不需要"}</Descriptions.Item>
              <Descriptions.Item label="网络需求">{activeModel.requires?.network ? "需要" : "不需要"}</Descriptions.Item>
              <Descriptions.Item label="GPU 需求">{activeModel.requires?.gpu ? "需要" : "不需要"}</Descriptions.Item>
              <Descriptions.Item label="本地权重">{activeModel.requires?.local_weights ? "需要" : "不需要"}</Descriptions.Item>
            </Descriptions>

            {activeModel.runtime ? (
              <>
                <Divider />
                <Descriptions title="运行时配置" column={1} bordered size="small">
                  <Descriptions.Item label="API Key 环境变量">{activeModel.runtime.api_key_env || "未配置"}</Descriptions.Item>
                  <Descriptions.Item label="API URL 环境变量">{activeModel.runtime.api_url_env || "未配置"}</Descriptions.Item>
                  <Descriptions.Item label="Confidence 环境变量">{activeModel.runtime.confidence_env || "未配置"}</Descriptions.Item>
                </Descriptions>
              </>
            ) : null}

            {activeModel.metrics ? (
              <>
                <Divider />
                <Descriptions title="最近验证结果" column={2} bordered size="small">
                  <Descriptions.Item label="验证来源">{activeModel.metrics.source || "未配置"}</Descriptions.Item>
                  <Descriptions.Item label="测试图片数">{activeModel.metrics.tested_count ?? "未配置"}</Descriptions.Item>
                  <Descriptions.Item label="扫描图片总数">{activeModel.metrics.scanned_image_count ?? "未配置"}</Descriptions.Item>
                  <Descriptions.Item label="有检测图片数">{activeModel.metrics.images_with_detections ?? "未配置"}</Descriptions.Item>
                  <Descriptions.Item label="总检测框数">{activeModel.metrics.total_detections ?? "未配置"}</Descriptions.Item>
                </Descriptions>
              </>
            ) : null}

            <Divider />
            <Typography.Title level={5}>限制说明</Typography.Title>
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              {(activeModel.limitations || []).map((item) => (
                <Alert key={item} type="info" showIcon message={item} />
              ))}
            </Space>
          </Space>
        ) : null}
      </Drawer>
    </>
  );
}
