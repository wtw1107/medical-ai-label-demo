import { EyeOutlined } from "@ant-design/icons";
import { Alert, Button, Descriptions, Drawer, Empty, Image, Space, Tag, Typography } from "antd";

import type { PredictionPreviewItem, PredictionPreviewResponse } from "../types/api";

interface PredictionPreviewProps {
  open: boolean;
  loading?: boolean;
  preview: PredictionPreviewResponse | null;
  onClose: () => void;
  onEnterLabel?: () => void;
}

function renderOverlay(predictions: PredictionPreviewItem[]) {
  return (
    <svg className="prediction-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
      {predictions.map((item, index) => {
        if (item.type === "rectanglelabels") {
          return (
            <g key={`${item.type}-${index}`}>
              <rect
                x={item.value.x || 0}
                y={item.value.y || 0}
                width={item.value.width || 0}
                height={item.value.height || 0}
                className="prediction-rect"
              />
              <text x={(item.value.x || 0) + 1} y={(item.value.y || 0) + 3} className="prediction-label">
                {item.label}
              </text>
            </g>
          );
        }

        const points = (item.value.points || []).map((point) => point.join(",")).join(" ");
        return (
          <g key={`${item.type}-${index}`}>
            <polygon points={points} className="prediction-polygon" />
            {item.value.points?.[0] ? (
              <text x={item.value.points[0][0] + 1} y={item.value.points[0][1] + 3} className="prediction-label">
                {item.label}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}

export function PredictionPreview({ open, loading, preview, onClose, onEnterLabel }: PredictionPreviewProps) {
  return (
    <Drawer
      title="AI 结果只读预览"
      placement="right"
      width={720}
      onClose={onClose}
      open={open}
      extra={
        <Space>
          <Button icon={<EyeOutlined />} onClick={onEnterLabel} disabled={!preview?.label_studio_task_url}>
            进入标注
          </Button>
        </Space>
      }
    >
      {loading ? (
        <Alert type="info" showIcon message="正在加载 AI prediction 预览..." />
      ) : !preview ? (
        <Empty description="暂无预览数据" />
      ) : !preview.has_prediction ? (
        <Empty description="当前图像暂无 AI 预标注结果，请先触发 AI 预标注并同步状态。" />
      ) : (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Alert
            type="info"
            showIcon
            message="这里是只读预览，用于快速检查 AI 结果。正式编辑和人工确认仍在 Label Studio 工作台中完成。"
          />
          <div className="prediction-preview-stage">
            <Image src={preview.image_url} alt={preview.filename} preview={false} className="prediction-preview-image" />
            {renderOverlay(preview.predictions)}
          </div>
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="文件名">{preview.filename}</Descriptions.Item>
            <Descriptions.Item label="图像尺寸">
              {preview.image_width || "-"} x {preview.image_height || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="模型 ID">{preview.model_id || "未知"}</Descriptions.Item>
            <Descriptions.Item label="模型版本">{preview.model_version || "未知"}</Descriptions.Item>
            <Descriptions.Item label="模型类型">{preview.model_type || "未知"}</Descriptions.Item>
            <Descriptions.Item label="Label Studio Task ID">{preview.label_studio_task_id || "未同步"}</Descriptions.Item>
            <Descriptions.Item label="Prediction 记录数">{preview.raw_prediction_count}</Descriptions.Item>
          </Descriptions>
          <div className="prediction-metadata-list">
            {preview.predictions.map((item, index) => (
              <div key={`${item.type}-${index}`} className="prediction-metadata-card">
                <Space wrap>
                  <Tag color="blue">{item.type}</Tag>
                  <Tag color="green">{item.label}</Tag>
                  <Tag>{item.score != null ? `score: ${item.score.toFixed(2)}` : "score: -"}</Tag>
                  {item.model_id ? <Tag color="purple">{item.model_id}</Tag> : null}
                  {item.model_type ? <Tag>{item.model_type}</Tag> : null}
                  {item.model_version ? <Tag>{item.model_version}</Tag> : null}
                </Space>
                {item.created_at ? (
                  <Typography.Text type="secondary">生成时间：{item.created_at}</Typography.Text>
                ) : null}
              </div>
            ))}
          </div>
          <Typography.Text type="secondary">
            预览使用 Label Studio 百分比坐标直接绘制 overlay，不会修改任何标注数据。
          </Typography.Text>
        </Space>
      )}
    </Drawer>
  );
}
