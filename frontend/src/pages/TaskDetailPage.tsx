import { Alert, Button, Card, Descriptions, Empty, Space, Tabs, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getPredictionPreview, getTaskImages, syncLabelStudioStatus } from "../api/prelabel";
import { getLabelStudioUrl, getTaskDetail } from "../api/tasks";
import { ExportPanel } from "../components/ExportPanel";
import { ImageStatusTable } from "../components/ImageStatusTable";
import { PredictionPreview } from "../components/PredictionPreview";
import { PrelabelPanel } from "../components/PrelabelPanel";
import { StatusTag } from "../components/StatusTag";
import { WorkbenchPanel } from "../components/WorkbenchPanel";
import type { AnnotationTaskDetail, PredictionPreviewResponse, TaskImageStatusItem } from "../types/api";

export function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<AnnotationTaskDetail | null>(null);
  const [images, setImages] = useState<TaskImageStatusItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncingStatus, setSyncingStatus] = useState(false);
  const [activeTabKey, setActiveTabKey] = useState("overview");
  const [selectedWorkbenchImage, setSelectedWorkbenchImage] = useState<TaskImageStatusItem | null>(null);
  const [iframeRefreshKey, setIframeRefreshKey] = useState(0);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewImage, setPreviewImage] = useState<TaskImageStatusItem | null>(null);
  const [previewData, setPreviewData] = useState<PredictionPreviewResponse | null>(null);

  useEffect(() => {
    if (!taskId) {
      return;
    }

    const currentTaskId = taskId;
    let active = true;

    async function loadTaskData() {
      try {
        setLoading(true);
        const [taskDetail, taskImages] = await Promise.all([
          getTaskDetail(currentTaskId),
          getTaskImages(currentTaskId),
        ]);
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
        message.error(error instanceof Error ? error.message : "加载任务详情失败。");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadTaskData();

    return () => {
      active = false;
    };
  }, [taskId]);

  const refreshTask = async () => {
    if (!taskId) {
      return;
    }

    try {
      setLoading(true);
      const [taskDetail, taskImages] = await Promise.all([getTaskDetail(taskId), getTaskImages(taskId)]);
      setTask(taskDetail);
      setImages(taskImages.images);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "刷新任务状态失败。");
    } finally {
      setLoading(false);
    }
  };

  const handleSyncLabelStudioStatus = async () => {
    if (!taskId) {
      return;
    }

    try {
      setSyncingStatus(true);
      const result = await syncLabelStudioStatus(taskId);
      setImages(result.images);
      await refreshTask();
      message.success(
        `同步完成：共 ${result.synced_count} 张图像，${result.prediction_written_count} 张已写入 prediction，${result.annotation_saved_count} 张已保存 annotation。`,
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : "同步 Label Studio 状态失败。");
    } finally {
      setSyncingStatus(false);
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
      message.error(error instanceof Error ? error.message : "打开 Label Studio 失败。");
    }
  };

  const handleEnterLabel = (image: TaskImageStatusItem) => {
    if (!image.label_studio_task_url) {
      message.warning("暂无 task URL，请先同步或重新创建任务。");
      return;
    }

    setSelectedWorkbenchImage(image);
    setActiveTabKey("workbench");
    setIframeRefreshKey((value) => value + 1);
  };

  const handlePreviewPrediction = async (image: TaskImageStatusItem) => {
    if (!taskId) {
      return;
    }

    try {
      setPreviewOpen(true);
      setPreviewLoading(true);
      setPreviewImage(image);
      const preview = await getPredictionPreview(taskId, image.image_id);
      setPreviewData(preview);
    } catch (error) {
      setPreviewData(null);
      message.error(error instanceof Error ? error.message : "加载 AI 预览失败。");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleEnterLabelFromPreview = () => {
    if (!previewImage) {
      return;
    }
    setPreviewOpen(false);
    handleEnterLabel(previewImage);
  };

  const selectedImage = useMemo(() => {
    if (!selectedWorkbenchImage) {
      return null;
    }
    return images.find((image) => image.image_id === selectedWorkbenchImage.image_id) || selectedWorkbenchImage;
  }, [images, selectedWorkbenchImage]);

  const imageStats = useMemo(() => {
    const predictionWritten = images.filter((image) => image.prediction_status === "written").length;
    const predictionFailed = images.filter((image) => image.prediction_status === "failed").length;
    const annotationSaved = images.filter((image) => image.annotation_status === "saved").length;
    return {
      total: images.length,
      predictionWritten,
      predictionFailed,
      annotationSaved,
    };
  }, [images]);

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
            这里汇总当前 AI 辅助标注任务的关键状态。你可以在本页查看图像状态、同步 Label Studio 状态、选择模型触发预标注、预览只读 AI 结果，并在需要时进入工作台完成人工确认和导出。
          </Typography.Paragraph>
          <Space wrap>
            <Typography.Text>图像总数：{imageStats.total}</Typography.Text>
            <Typography.Text>Prediction 已写入：{imageStats.predictionWritten}</Typography.Text>
            <Typography.Text>Prediction 失败：{imageStats.predictionFailed}</Typography.Text>
            <Typography.Text>Annotation 已保存：{imageStats.annotationSaved}</Typography.Text>
          </Space>
          <Space wrap>
            <Button size="large" onClick={() => navigate("/tasks")}>
              返回任务列表
            </Button>
            <Button type="primary" size="large" onClick={handleOpenLabelStudio} disabled={!task}>
              在新窗口打开 Label Studio
            </Button>
            <Button size="large" onClick={() => void handleSyncLabelStudioStatus()} loading={syncingStatus}>
              同步 Label Studio 状态
            </Button>
            <Button size="large" onClick={() => void refreshTask()} loading={loading}>
              刷新任务状态
            </Button>
          </Space>
          {task?.error_message ? <Alert type="warning" showIcon message={task.error_message} /> : null}
        </Space>
      </Card>

      <Tabs
        activeKey={activeTabKey}
        onChange={setActiveTabKey}
        className="task-detail-tabs"
        items={[
          {
            key: "overview",
            label: "任务概览",
            children: (
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
                    <Descriptions.Item label="Label Studio 项目 ID">
                      {task.label_studio_project_id ?? "未初始化"}
                    </Descriptions.Item>
                  </Descriptions>
                ) : (
                  <Empty description="暂无任务信息" />
                )}
              </Card>
            ),
          },
          {
            key: "images",
            label: "图像状态",
            children: (
              <Card title="图像状态总览" className="panel-card" extra={<Typography.Text>共 {images.length} 张</Typography.Text>}>
                <ImageStatusTable
                  images={images}
                  loading={loading || syncingStatus}
                  onEnterLabel={handleEnterLabel}
                  onPreviewPrediction={(image) => void handlePreviewPrediction(image)}
                />
              </Card>
            ),
          },
          {
            key: "prelabel",
            label: "AI 预标注",
            children: (
              <PrelabelPanel
                taskId={taskId}
                taskType={task?.task_type || "bbox_polygon"}
                detModelId={task?.det_model_id}
                segModelId={task?.seg_model_id}
                onCompleted={refreshTask}
              />
            ),
          },
          {
            key: "workbench",
            label: "标注工作台",
            children: (
              <WorkbenchPanel
                projectUrl={task?.label_studio_project_url || null}
                taskUrl={selectedImage?.label_studio_task_url || null}
                selectedImageName={selectedImage?.filename || null}
                onOpenExternal={(url) => window.open(url, "_blank", "noopener,noreferrer")}
                refreshToken={iframeRefreshKey}
              />
            ),
          },
          {
            key: "export",
            label: "导出结果",
            children: <ExportPanel taskId={taskId} images={images} onExported={refreshTask} />,
          },
        ]}
      />

      <PredictionPreview
        open={previewOpen}
        loading={previewLoading}
        preview={previewData}
        onClose={() => {
          setPreviewOpen(false);
          setPreviewData(null);
          setPreviewImage(null);
        }}
        onEnterLabel={() => handleEnterLabelFromPreview()}
      />
    </Space>
  );
}
