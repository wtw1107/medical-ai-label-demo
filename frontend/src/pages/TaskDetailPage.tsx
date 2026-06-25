import { Alert, Button, Card, Col, Descriptions, Empty, Row, Space, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getTaskImages } from "../api/prelabel";
import { getLabelStudioUrl, getTaskDetail } from "../api/tasks";
import { ExportPanel } from "../components/ExportPanel";
import { ImageStatusTable } from "../components/ImageStatusTable";
import { PrelabelPanel } from "../components/PrelabelPanel";
import { StatusTag } from "../components/StatusTag";
import type { AnnotationTaskDetail, TaskImageStatusItem } from "../types/api";

export function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const [task, setTask] = useState<AnnotationTaskDetail | null>(null);
  const [images, setImages] = useState<TaskImageStatusItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!taskId) {
      return;
    }

    const currentTaskId = taskId;
    let active = true;

    async function load() {
      try {
        setLoading(true);
        const [taskDetail, taskImages] = await Promise.all([getTaskDetail(currentTaskId), getTaskImages(currentTaskId)]);
        if (!active) {
          return;
        }
        setTask(taskDetail);
        setImages(taskImages.images);
      } catch (error) {
        if (!active) {
          return;
        }
        setTask(null);
        setImages([]);
        message.error(error instanceof Error ? error.message : "加载任务详情失败");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [taskId]);

  const refreshTask = async () => {
    if (!taskId) {
      return;
    }

    const currentTaskId = taskId;
    try {
      setLoading(true);
      const [taskDetail, taskImages] = await Promise.all([getTaskDetail(currentTaskId), getTaskImages(currentTaskId)]);
      setTask(taskDetail);
      setImages(taskImages.images);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "刷新任务状态失败");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenLabelStudio = async () => {
    if (!taskId) {
      return;
    }
    try {
      const result = await getLabelStudioUrl(taskId);
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "打开 Label Studio 失败");
    }
  };

  if (!taskId) {
    return <Empty description="未找到任务 ID" />;
  }

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Space wrap>
            <Typography.Title level={2} className="detail-title">
              {task?.name || "任务详情"}
            </Typography.Title>
            {task ? <StatusTag status={task.status} /> : null}
          </Space>
          <Typography.Paragraph className="hero-description">
            这里展示当前 AI 辅助标注任务的核心状态。你可以先触发预标注，再跳转 Label Studio 完成人工审核，最后回到这里发起导出。
          </Typography.Paragraph>
          <Space wrap>
            <Button type="primary" size="large" onClick={handleOpenLabelStudio} disabled={!task}>
              打开 Label Studio 工作台
            </Button>
            <Button size="large" onClick={() => void refreshTask()} loading={loading}>
              刷新任务状态
            </Button>
          </Space>
          {task?.error_message ? <Alert type="warning" showIcon message={task.error_message} /> : null}
        </Space>
      </Card>

      <Row gutter={[24, 24]}>
        <Col xs={24} xl={10}>
          <Card title="任务信息" className="panel-card" loading={loading}>
            {task ? (
              <Descriptions column={1} size="small">
                <Descriptions.Item label="任务 ID">{task.task_id}</Descriptions.Item>
                <Descriptions.Item label="数据集 ID">{task.dataset_id}</Descriptions.Item>
                <Descriptions.Item label="任务类型">{task.task_type}</Descriptions.Item>
                <Descriptions.Item label="标签名称">{task.label_name}</Descriptions.Item>
                <Descriptions.Item label="检测模型">{task.det_model_id || "未设置"}</Descriptions.Item>
                <Descriptions.Item label="分割模型">{task.seg_model_id || "未设置"}</Descriptions.Item>
                <Descriptions.Item label="人工确认">{task.require_human_confirm ? "需要" : "不需要"}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Empty description="暂无任务信息" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <PrelabelPanel taskId={taskId} onCompleted={refreshTask} />
        </Col>
      </Row>

      <Card
        title="图像状态总览"
        className="panel-card"
        extra={<Typography.Text>共 {images.length} 张</Typography.Text>}
      >
        <ImageStatusTable images={images} loading={loading} />
      </Card>

      <ExportPanel taskId={taskId} onExported={refreshTask} />
    </Space>
  );
}
