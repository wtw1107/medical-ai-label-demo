import React from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Drawer,
  List,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";

import { listModels } from "../api/models";
import { getPrelabelJob, runPrelabel } from "../api/prelabel";
import type {
  ModelInfo,
  ModelMetrics,
  ModelRequirements,
  ModelRuntime,
  PrelabelJobStatusResponse,
  TaskType,
} from "../types/api";
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
    requires: {
      api_key: false,
      network: false,
      gpu: false,
      local_weights: false,
    },
    limitations: ["Synthetic demo predictions.", "Not a real AI model.", "Use only for workflow testing."],
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
    requires: {
      api_key: false,
      network: false,
      gpu: false,
      local_weights: false,
    },
    limitations: ["Synthetic demo polygons.", "Not a real segmentation model.", "Use only for workflow testing."],
  },
];

const statusText: Record<string, string> = {
  available: "可用",
  not_configured: "未配置",
};

const statusColorMap: Record<string, string> = {
  available: "success",
  not_configured: "default",
  mock: "processing",
  external_api: "purple",
  local_model_placeholder: "gold",
};

const modelTypeText: Record<string, string> = {
  detection: "目标检测",
  segmentation: "分割",
};

const deploymentText: Record<string, string> = {
  external_api: "外部 API",
  mock: "演示模型",
  local_model_placeholder: "本地模型占位",
};

const valueText: Record<string, string> = {
  bbox: "目标框",
  bbox_polygon: "框 + 多边形",
  polygon: "多边形",
  metadata: "元数据",
  confidence: "置信度",
  detection: "目标检测",
  segmentation: "分割",
};

const limitationTextMap: Record<string, string> = {
  "Synthetic demo predictions.": "模拟生成的演示预测结果。",
  "Not a real AI model.": "不是真实 AI 模型。",
  "Use only for workflow testing.": "仅用于流程测试。",
  "Synthetic demo polygons.": "模拟生成的演示轮廓结果。",
  "Not a real segmentation model.": "不是真实分割模型。",
  "Demo-only model for AI-assisted pre-annotation.": "仅用于 AI 辅助预标注演示。",
  "Not for clinical diagnosis.": "不用于临床诊断。",
  "Calls an external Roboflow API; images may be sent to a third-party service.":
    "会调用外部 Roboflow API，图像可能发送到第三方服务。",
  "Performance may vary across ultrasound devices and image distributions.":
    "在不同超声设备和图像分布上的表现可能存在差异。",
  "0 detections will not be written as empty predictions.": "返回 0 detections 时不会写入空 prediction。",
  "Not configured yet.": "当前尚未配置。",
  "Local model weights are required before use.": "使用前需要准备本地模型权重。",
  "This model cannot be selected for prelabel until configured.": "完成配置前不能用于预标注。",
};

function getDeploymentLabel(value?: string | null) {
  if (!value) {
    return "暂无信息";
  }
  return deploymentText[value] || value;
}

function getModelTypeLabel(value?: string | null) {
  if (!value) {
    return "暂无信息";
  }
  return modelTypeText[value] || value;
}

function getValueLabel(value: string) {
  return valueText[value] || value;
}

function renderBooleanRequirement(value: boolean | null | undefined) {
  if (value == null) {
    return "暂无信息";
  }
  return value ? "需要" : "不需要";
}

function renderListValue(items?: string[] | null, emptyText = "暂无信息") {
  if (!items || items.length === 0) {
    return emptyText;
  }
  return items.map((item) => getValueLabel(item)).join(" / ");
}

function renderLimitationText(value: string) {
  return limitationTextMap[value] || value;
}

function getModelDisplayName(model: ModelInfo | null) {
  if (!model) {
    return "暂无模型";
  }
  if (model.model_id === "mock_segmentation") {
    return "演示分割模型";
  }
  return model.model_name;
}

function buildRiskMessage(model: ModelInfo | null) {
  if (!model) {
    return null;
  }
  if (model.deployment_type === "external_api") {
    return {
      type: "warning" as const,
      message: "该模型通过外部 API 调用。请确认当前数据允许发送到外部服务。",
    };
  }
  if (model.deployment_type === "mock") {
    return {
      type: "info" as const,
      message: "该模型仅用于流程演示，不代表真实 AI 预测。",
    };
  }
  if (model.status === "not_configured") {
    return {
      type: "warning" as const,
      message: "该模型尚未配置，当前不可用于预标注。",
    };
  }
  return null;
}

function ModelSummaryCard({
  model,
  title,
  onOpenDetails,
}: {
  model: ModelInfo | null;
  title: string;
  onOpenDetails: () => void;
}) {
  const riskMessage = buildRiskMessage(model);

  return (
    <Card
      className="model-summary-card"
      title={title}
      extra={
        model ? (
          <Space wrap>
            <Tag color={statusColorMap[model.status] || "default"}>{statusText[model.status] || model.status}</Tag>
            <Tag color={statusColorMap[model.deployment_type || ""] || "default"}>
              {getDeploymentLabel(model.deployment_type)}
            </Tag>
          </Space>
        ) : null
      }
    >
      {model ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <div>
            <Typography.Title level={5} style={{ margin: 0 }}>
              {getModelDisplayName(model)}
            </Typography.Title>
            <Typography.Paragraph className="muted-paragraph" style={{ marginTop: 6 }}>
              {model.model_id === "mock_segmentation"
                ? "演示分割模型，用于补全 bbox_polygon 工作流。"
                : model.description}
            </Typography.Paragraph>
          </div>

          {riskMessage ? <Alert type={riskMessage.type} showIcon message={riskMessage.message} /> : null}

          <Descriptions size="small" column={1}>
            <Descriptions.Item label="模型 ID">{model.model_id}</Descriptions.Item>
            <Descriptions.Item label="版本">{model.model_version}</Descriptions.Item>
            <Descriptions.Item label="Provider">{model.provider || "暂无信息"}</Descriptions.Item>
            <Descriptions.Item label="任务类型">{renderListValue(model.task_types)}</Descriptions.Item>
            <Descriptions.Item label="输出类型">{renderListValue(model.outputs)}</Descriptions.Item>
          </Descriptions>

          <Space wrap>
            <Tag color="blue">{getModelTypeLabel(model.model_type)}</Tag>
            {model.task_types?.map((item) => (
              <Tag key={item}>{getValueLabel(item)}</Tag>
            ))}
            {model.outputs?.map((item) => (
              <Tag key={`${model.model_id}-${item}`} color="geekblue">
                {getValueLabel(item)}
              </Tag>
            ))}
          </Space>

          <Button block onClick={onOpenDetails}>
            查看详情
          </Button>
        </Space>
      ) : (
        <Typography.Text type="secondary">当前任务没有对应的模型信息。</Typography.Text>
      )}
    </Card>
  );
}

function ModelCapabilitiesCard({ model }: { model: ModelInfo | null }) {
  const metrics = model?.metrics;

  return (
    <Card className="model-summary-card" title="运行摘要">
      {model ? (
        <Space direction="vertical" size={14} style={{ width: "100%" }}>
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="适用部位">{renderListValue(model.anatomy, "不需要")}</Descriptions.Item>
            <Descriptions.Item label="模态">{renderListValue(model.modality, "不需要")}</Descriptions.Item>
            <Descriptions.Item label="API Key">{renderBooleanRequirement(model.requires?.api_key)}</Descriptions.Item>
            <Descriptions.Item label="网络">{renderBooleanRequirement(model.requires?.network)}</Descriptions.Item>
            <Descriptions.Item label="GPU">{renderBooleanRequirement(model.requires?.gpu)}</Descriptions.Item>
            <Descriptions.Item label="本地权重">
              {renderBooleanRequirement(model.requires?.local_weights)}
            </Descriptions.Item>
          </Descriptions>

          <Alert
            type="info"
            showIcon
            message={
              model.runtime?.confidence_env
                ? `当前 confidence 由模型服务环境变量 ${model.runtime.confidence_env} 控制。如需调整阈值，请更新模型服务配置后重新运行预标注。`
                : "当前没有额外的 confidence 环境变量说明。"
            }
          />

          {metrics ? (
            <>
              <Row gutter={[12, 12]}>
                <Col span={12}>
                  <Statistic title="测试图片数" value={metrics.tested_count ?? "-"} />
                </Col>
                <Col span={12}>
                  <Statistic title="有检测图片数" value={metrics.images_with_detections ?? "-"} />
                </Col>
                <Col span={12}>
                  <Statistic title="API 成功次数" value={metrics.api_success_count ?? "-"} />
                </Col>
                <Col span={12}>
                  <Statistic title="总检测框数" value={metrics.total_detections ?? "-"} />
                </Col>
              </Row>
              <Typography.Text type="secondary">
                该结果为本地连通性与样例验证结果，不代表模型临床性能。
              </Typography.Text>
            </>
          ) : (
            <Typography.Text type="secondary">暂无最近验证结果。</Typography.Text>
          )}
        </Space>
      ) : (
        <Typography.Text type="secondary">暂无运行摘要。</Typography.Text>
      )}
    </Card>
  );
}

function RequirementsSection({ requires }: { requires?: ModelRequirements | null }) {
  return (
    <Descriptions title="运行要求" bordered column={2} size="small">
      <Descriptions.Item label="API Key">{renderBooleanRequirement(requires?.api_key)}</Descriptions.Item>
      <Descriptions.Item label="网络">{renderBooleanRequirement(requires?.network)}</Descriptions.Item>
      <Descriptions.Item label="GPU">{renderBooleanRequirement(requires?.gpu)}</Descriptions.Item>
      <Descriptions.Item label="本地权重">{renderBooleanRequirement(requires?.local_weights)}</Descriptions.Item>
    </Descriptions>
  );
}

function RuntimeSection({ runtime }: { runtime?: ModelRuntime | null }) {
  return (
    <Descriptions title="配置要求" bordered column={1} size="small">
      <Descriptions.Item label="API Key 环境变量">{runtime?.api_key_env || "暂无信息"}</Descriptions.Item>
      <Descriptions.Item label="API URL 环境变量">{runtime?.api_url_env || "暂无信息"}</Descriptions.Item>
      <Descriptions.Item label="模型 ID 环境变量">{runtime?.model_id_env || "暂无信息"}</Descriptions.Item>
      <Descriptions.Item label="Confidence 环境变量">
        {runtime?.confidence_env || "暂无信息"}
      </Descriptions.Item>
    </Descriptions>
  );
}

function MetricsSection({ metrics }: { metrics?: ModelMetrics | null }) {
  if (!metrics) {
    return <Typography.Text type="secondary">暂无最近验证结果。</Typography.Text>;
  }

  return (
    <Space direction="vertical" size={10} style={{ width: "100%" }}>
      <Descriptions title="最近验证结果" bordered column={2} size="small">
        <Descriptions.Item label="验证来源">{metrics.source || "暂无信息"}</Descriptions.Item>
        <Descriptions.Item label="confidence">{metrics.confidence ?? "暂无信息"}</Descriptions.Item>
        <Descriptions.Item label="扫描图片总数">{metrics.scanned_image_count ?? "暂无信息"}</Descriptions.Item>
        <Descriptions.Item label="测试图片数">{metrics.tested_count ?? "暂无信息"}</Descriptions.Item>
        <Descriptions.Item label="API 成功次数">{metrics.api_success_count ?? "暂无信息"}</Descriptions.Item>
        <Descriptions.Item label="有检测图片数">{metrics.images_with_detections ?? "暂无信息"}</Descriptions.Item>
        <Descriptions.Item label="总检测框数">{metrics.total_detections ?? "暂无信息"}</Descriptions.Item>
      </Descriptions>
      <Typography.Text type="secondary">
        该结果为本地连通性与样例验证结果，不代表模型临床性能。
      </Typography.Text>
    </Space>
  );
}

function LimitationsSection({ model }: { model: ModelInfo }) {
  const externalRisk = model.limitations?.find((item) => item.includes("third-party service"));
  const otherLimitations = (model.limitations || []).filter((item) => item !== externalRisk);

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {externalRisk ? <Alert type="warning" showIcon message={renderLimitationText(externalRisk)} /> : null}
      {otherLimitations.length > 0 ? (
        <List
          size="small"
          bordered
          dataSource={otherLimitations}
          renderItem={(item) => <List.Item>{renderLimitationText(item)}</List.Item>}
        />
      ) : (
        <Typography.Text type="secondary">暂无限制说明。</Typography.Text>
      )}
    </Space>
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

  const sidebarModel =
    taskType === "bbox"
      ? selectedDetectionModel
      : taskType === "polygon"
        ? selectedSegmentationModel
        : selectedSegmentationModel || selectedDetectionModel;

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
      <Card title="AI 预标注" extra={<StatusTag status={job?.status || "created"} />} className="panel-card">
        <Space direction="vertical" size={18} style={{ width: "100%" }}>
          <Alert
            type="info"
            showIcon
            message="这里负责调用后端模型服务，为当前任务写入 bbox / polygon 预标注。你可以先查看模型摘要、适用范围、配置要求和最近验证结果，再决定是否触发。"
          />

          {modelsError ? <Alert type="warning" showIcon message={modelsError} /> : null}
          {job?.error_message ? <Alert type="warning" showIcon message={job.error_message} /> : null}

          <Row gutter={[16, 16]} align="stretch">
            {(taskType === "bbox" || taskType === "bbox_polygon") ? (
              <Col xs={24} xl={12}>
                <ModelSummaryCard
                  model={selectedDetectionModel}
                  title="当前检测模型"
                  onOpenDetails={() => {
                    setActiveModelId(selectedDetectionModelId);
                    setDetailsOpen(true);
                  }}
                />
              </Col>
            ) : null}

            {(taskType === "polygon" || taskType === "bbox_polygon") ? (
              <Col xs={24} xl={12}>
                <ModelSummaryCard
                  model={selectedSegmentationModel}
                  title="当前分割模型"
                  onOpenDetails={() => {
                    setActiveModelId(selectedSegmentationModelId);
                    setDetailsOpen(true);
                  }}
                />
              </Col>
            ) : null}

            {taskType !== "bbox_polygon" ? (
              <Col xs={24} xl={12}>
                <ModelCapabilitiesCard model={sidebarModel} />
              </Col>
            ) : null}
          </Row>

          <Row gutter={[16, 16]}>
            {(taskType === "bbox" || taskType === "bbox_polygon") ? (
              <Col xs={24} xl={taskType === "bbox_polygon" ? 12 : 24}>
                <div className="model-control-block">
                  <Typography.Text strong>检测模型</Typography.Text>
                  <Select
                    style={{ width: "100%", marginTop: 8 }}
                    value={selectedDetectionModelId}
                    onChange={setSelectedDetectionModelId}
                    options={detectionModels.map((model) => ({
                      value: model.model_id,
                      label: `${getModelDisplayName(model)} (${statusText[model.status] || model.status})`,
                    }))}
                  />
                  {selectedDetectionModel ? (
                    <Typography.Paragraph className="muted-paragraph" style={{ marginTop: 8 }}>
                      {selectedDetectionModel.description}
                    </Typography.Paragraph>
                  ) : null}
                </div>
              </Col>
            ) : null}

            {(taskType === "polygon" || taskType === "bbox_polygon") ? (
              <Col xs={24} xl={taskType === "bbox_polygon" ? 12 : 24}>
                <div className="model-control-block">
                  <Typography.Text strong>分割模型</Typography.Text>
                  <Select
                    style={{ width: "100%", marginTop: 8 }}
                    value={selectedSegmentationModelId}
                    onChange={setSelectedSegmentationModelId}
                    options={segmentationModels.map((model) => ({
                      value: model.model_id,
                      label: `${getModelDisplayName(model)} (${statusText[model.status] || model.status})`,
                    }))}
                  />
                  {selectedSegmentationModel ? (
                    <Typography.Paragraph className="muted-paragraph" style={{ marginTop: 8 }}>
                      {selectedSegmentationModel.model_id === "mock_segmentation"
                        ? "演示分割模型，用于补全 bbox_polygon 工作流。"
                        : selectedSegmentationModel.description}
                    </Typography.Paragraph>
                  ) : null}
                </div>
              </Col>
            ) : null}
          </Row>

          {selectedDetectionModel?.status === "not_configured" || selectedSegmentationModel?.status === "not_configured" ? (
            <Alert
              type="warning"
              showIcon
              message="当前已选模型中包含未配置项。该模型在完成配置前不能用于预标注。"
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

          <Alert
            type="info"
            showIcon
            message="如果模型对某张图返回 0 detections，该图不会写入空 prediction，也不会导致整个任务失败。"
          />

          <div className="prelabel-action-row">
            <Button type="primary" size="large" loading={submitting} onClick={handleRunPrelabel}>
              触发 AI 预标注
            </Button>
          </div>
        </Space>
      </Card>

      <Drawer
        title={activeModel ? `${getModelDisplayName(activeModel)} 详情` : "模型详情"}
        open={detailsOpen}
        width={820}
        onClose={() => setDetailsOpen(false)}
      >
        {activeModel ? (
          <Space direction="vertical" size={20} style={{ width: "100%" }}>
            {buildRiskMessage(activeModel) ? (
              <Alert type={buildRiskMessage(activeModel)?.type} showIcon message={buildRiskMessage(activeModel)?.message} />
            ) : null}

            <Descriptions title="基础信息" bordered column={2} size="small">
              <Descriptions.Item label="模型名称">{getModelDisplayName(activeModel)}</Descriptions.Item>
              <Descriptions.Item label="模型 ID">{activeModel.model_id}</Descriptions.Item>
              <Descriptions.Item label="版本">{activeModel.model_version}</Descriptions.Item>
              <Descriptions.Item label="模型类型">{getModelTypeLabel(activeModel.model_type)}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColorMap[activeModel.status] || "default"}>
                  {statusText[activeModel.status] || activeModel.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="部署方式">
                <Tag color={statusColorMap[activeModel.deployment_type || ""] || "default"}>
                  {getDeploymentLabel(activeModel.deployment_type)}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Provider">{activeModel.provider || "暂无信息"}</Descriptions.Item>
            </Descriptions>

            <Descriptions title="适用范围" bordered column={2} size="small">
              <Descriptions.Item label="适用任务">{renderListValue(activeModel.task_types)}</Descriptions.Item>
              <Descriptions.Item label="适用部位">{renderListValue(activeModel.anatomy, "不需要")}</Descriptions.Item>
              <Descriptions.Item label="模态">{renderListValue(activeModel.modality, "不需要")}</Descriptions.Item>
              <Descriptions.Item label="输出类型">{renderListValue(activeModel.outputs)}</Descriptions.Item>
            </Descriptions>

            <RequirementsSection requires={activeModel.requires} />
            <RuntimeSection runtime={activeModel.runtime} />
            <MetricsSection metrics={activeModel.metrics} />

            <Divider />
            <Typography.Title level={5}>使用限制</Typography.Title>
            <LimitationsSection model={activeModel} />
          </Space>
        ) : null}
      </Drawer>
    </>
  );
}
