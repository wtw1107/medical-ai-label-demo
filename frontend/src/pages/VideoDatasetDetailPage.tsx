import React, { useEffect, useMemo, useState } from "react";
import { Alert, App, Button, Card, Descriptions, Empty, Image, Space, Table, Tabs, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useNavigate, useParams } from "react-router-dom";

import {
  exportBlineKeyframes,
  getCvatHealth,
  getVideoDataset,
  initDatasetCvat,
  listDatasetVideos,
  syncDatasetCvat,
} from "../api/videos";
import { StatusTag } from "../components/StatusTag";
import type { CvatHealthResponse, ReviewSummaryItem, SplitSummaryItem, VideoDatasetSummary, VideoItem } from "../types/api";

function formatNumber(value?: number | null, fractionDigits = 1) {
  if (value == null) {
    return "-";
  }
  return value.toFixed(fractionDigits);
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function renderSplitSummary(items: SplitSummaryItem[]) {
  if (items.length === 0) {
    return <Typography.Text type="secondary">暂无 split 摘要</Typography.Text>;
  }
  return (
    <Space wrap>
      {items.map((item) => (
        <Tag key={item.split}>{`${item.split}: 患者 ${item.patient_count} / 视频 ${item.video_count}`}</Tag>
      ))}
    </Space>
  );
}

function renderReviewSummary(items: ReviewSummaryItem[]) {
  if (items.length === 0) {
    return <Typography.Text type="secondary">暂无 review 摘要</Typography.Text>;
  }
  return (
    <Space wrap>
      {items.map((item) => (
        <Tag key={item.quality} color={item.quality === "good" ? "success" : item.quality === "poor" ? "error" : "default"}>
          {`${item.quality}: ${item.count}`}
        </Tag>
      ))}
    </Space>
  );
}

export function VideoDatasetDetailPage() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [summary, setSummary] = useState<VideoDatasetSummary | null>(null);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [cvatHealth, setCvatHealth] = useState<CvatHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [initializingCvat, setInitializingCvat] = useState(false);
  const [syncingCvat, setSyncingCvat] = useState(false);

  const loadData = async (currentDatasetId: string) => {
    setLoading(true);
    try {
      const [summaryResponse, videosResponse, healthResponse] = await Promise.all([
        getVideoDataset(currentDatasetId),
        listDatasetVideos(currentDatasetId),
        getCvatHealth(),
      ]);
      setSummary(summaryResponse);
      setVideos(videosResponse.videos);
      setCvatHealth(healthResponse);
    } catch (error) {
      setSummary(null);
      setVideos([]);
      message.error(error instanceof Error ? error.message : "加载视频任务详情失败。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!datasetId) {
      return;
    }
    void loadData(datasetId);
  }, [datasetId]);

  const handleExport = async () => {
    if (!datasetId) {
      return;
    }
    try {
      setExporting(true);
      const result = await exportBlineKeyframes(datasetId);
      window.open(result.download_url, "_blank", "noopener,noreferrer");
      message.success(`导出完成：已标注 ${result.total_labeled_count} 帧，跳过 ${result.skipped_count} 帧。`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "导出 B-line 关键帧数据集失败。");
    } finally {
      setExporting(false);
    }
  };

  const handleInitCvat = async () => {
    if (!datasetId) {
      return;
    }
    if (summary?.annotation_backend === "label_studio") {
      message.warning("该视频任务使用 Label Studio 后端，当前不会自动迁移到 CVAT。");
      return;
    }
    try {
      setInitializingCvat(true);
      const result = await initDatasetCvat(datasetId);
      if (result.error) {
        message.warning(result.error);
      } else {
        message.success(`CVAT 初始化完成：新建 ${result.created_task_count} 个，复用 ${result.reused_task_count} 个。`);
      }
      await loadData(datasetId);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "初始化 CVAT 标注任务失败。");
    } finally {
      setInitializingCvat(false);
    }
  };

  const handleSyncCvat = async () => {
    if (!datasetId) {
      return;
    }
    try {
      setSyncingCvat(true);
      const result = await syncDatasetCvat(datasetId);
      if (result.error) {
        message.warning(result.error);
      } else {
        message.success("CVAT 状态同步完成。");
      }
      await loadData(datasetId);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "同步 CVAT 状态失败。");
    } finally {
      setSyncingCvat(false);
    }
  };

  const columns = useMemo<ColumnsType<VideoItem>>(
    () => [
      {
        title: "视频",
        key: "video",
        render: (_, record) => (
          <Space size={12}>
            {record.preview_image_url ? (
              <Image
                src={record.preview_image_url}
                alt={record.filename}
                width={84}
                height={56}
                style={{ objectFit: "cover", borderRadius: 10 }}
                preview={false}
              />
            ) : null}
            <Space direction="vertical" size={0}>
              <Typography.Text strong>{record.filename}</Typography.Text>
              <Typography.Text type="secondary">{record.patient_uid || "未关联患者"}</Typography.Text>
            </Space>
          </Space>
        ),
      },
      {
        title: "肺区",
        dataIndex: "lung_zone",
        key: "lung_zone",
        render: (value) => value || "-",
      },
      {
        title: "时长 / FPS",
        key: "metrics",
        render: (_, record) => `${formatNumber(record.duration_sec, 1)}s / ${formatNumber(record.fps, 1)}`,
      },
      {
        title: "帧数 / 分辨率",
        key: "frames",
        render: (_, record) => `${record.frame_count ?? "-"} / ${record.width ?? "-"}x${record.height ?? "-"}`,
      },
      {
        title: "CVAT",
        key: "cvat",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Tag color={record.cvat_task_id ? "processing" : "default"}>{record.cvat_status || "not_initialized"}</Tag>
            <Typography.Text type="secondary">{record.cvat_task_id ? `task ${record.cvat_task_id}` : "未初始化"}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "质量",
        dataIndex: "quality",
        key: "quality",
        render: (value: string) => <Tag color={value === "good" ? "success" : value === "poor" ? "error" : "default"}>{value}</Tag>,
      },
      {
        title: "B 线等级",
        dataIndex: "bline_grade",
        key: "bline_grade",
      },
      {
        title: "关键帧",
        dataIndex: "keyframe_count",
        key: "keyframe_count",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        render: (value: string) => <StatusTag status={value} />,
      },
      {
        title: "操作",
        key: "actions",
        fixed: "right",
        render: (_, record) => (
          <Space>
            <Button onClick={() => navigate(`/video-datasets/${record.dataset_id}/videos/${record.id}`)}>查看视频</Button>
            <Button
              type="primary"
              disabled={!record.cvat_job_url && !record.cvat_task_url}
              onClick={() => window.open(record.cvat_job_url || record.cvat_task_url || "", "_blank", "noopener,noreferrer")}
            >
              打开 CVAT 标注
            </Button>
          </Space>
        ),
      },
    ],
    [navigate],
  );

  const summaryCard = (
    <Card title="任务概览" className="panel-card" loading={loading}>
      {summary ? (
        <Descriptions column={1} size="small">
          <Descriptions.Item label="dataset_id">{summary.dataset_id}</Descriptions.Item>
          <Descriptions.Item label="data_type">{summary.data_type}</Descriptions.Item>
          <Descriptions.Item label="annotation_backend">{summary.annotation_backend || "cvat/spike"}</Descriptions.Item>
          <Descriptions.Item label="CVAT Project">{summary.cvat_project_id || "-"}</Descriptions.Item>
          <Descriptions.Item label="任务类型">肺超声 B-line 视频关键帧分割</Descriptions.Item>
          <Descriptions.Item label="视频数">{summary.video_count}</Descriptions.Item>
          <Descriptions.Item label="患者数">{summary.patient_count}</Descriptions.Item>
          <Descriptions.Item label="关键帧总数">{summary.keyframe_count}</Descriptions.Item>
          <Descriptions.Item label="split 摘要">{renderSplitSummary(summary.split_summary)}</Descriptions.Item>
          <Descriptions.Item label="review 摘要">{renderReviewSummary(summary.review_status_summary)}</Descriptions.Item>
        </Descriptions>
      ) : (
        <Empty description="暂无任务概览" />
      )}
    </Card>
  );

  const cvatAlert = cvatHealth ? (
    <Alert
      type={cvatHealth.reachable && cvatHealth.authenticated ? "success" : "warning"}
      showIcon
      message={`CVAT: ${cvatHealth.reachable ? "reachable" : "unreachable"}`}
      description={
        cvatHealth.error ||
        `server_version=${cvatHealth.server_version || "unknown"}; review_supported=${String(cvatHealth.review_supported)}; consensus_supported=${String(
          cvatHealth.consensus_supported,
        )}`
      }
    />
  ) : null;

  const videoTable = (
    <Card
      title="视频列表"
      className="panel-card"
      extra={
        <Space>
          <Typography.Text>{`共 ${videos.length} 个视频`}</Typography.Text>
          <Button onClick={() => void handleInitCvat()} loading={initializingCvat} disabled={summary?.annotation_backend === "label_studio"}>
            初始化 CVAT 标注任务
          </Button>
          <Button onClick={() => void handleSyncCvat()} loading={syncingCvat}>
            同步 CVAT 状态
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {cvatAlert}
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={videos}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          scroll={{ x: 1400 }}
        />
        {!loading && videos.length === 0 ? <Empty description="暂无视频数据" /> : null}
        {!loading && videos.length > 0 ? (
          <Typography.Text type="secondary">
            最近一条审核时间：{formatDateTime(videos.find((video) => video.reviewed_at)?.reviewed_at)}
          </Typography.Text>
        ) : null}
      </Space>
    </Card>
  );

  if (!datasetId) {
    return <Empty description="未找到数据集 ID" />;
  }

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Title level={2} className="detail-title">
            {summary?.dataset_name || "视频任务详情"}
          </Typography.Title>
          <Typography.Paragraph className="hero-description">
            当前视频流程为：上传视频、查看完整视频、选择关键帧、标注 B-line、查看标注后的完整视频、复核与导出。CVAT 集成为本分支 spike，不影响图片 Label Studio 主链路。
          </Typography.Paragraph>
          <Space wrap>
            <Button onClick={() => navigate("/tasks")}>返回任务列表</Button>
            <Button onClick={() => navigate("/")}>上传新数据</Button>
            <Button onClick={() => void loadData(datasetId)} loading={loading}>
              刷新
            </Button>
          </Space>
        </Space>
      </Card>

      <Tabs
        items={[
          {
            key: "overview",
            label: "任务概览",
            children: summaryCard,
          },
          {
            key: "video-keyframes",
            label: "视频预览与关键帧标注",
            children: videoTable,
          },
          {
            key: "video-recheck",
            label: "标注后视频复看",
            children: (
              <Card className="panel-card">
                <Alert type="info" showIcon message="标注后完整视频复看需要 CVAT 标注结果叠加能力，本轮仅保留占位与集成评估。" />
              </Card>
            ),
          },
          {
            key: "review-flow",
            label: "复核",
            children: (
              <Card className="panel-card">
                <Alert type="info" showIcon message="复核、issue 与仲裁能力需依赖 CVAT 版本能力确认，本轮仅做 spike 骨架。" />
              </Card>
            ),
          },
          {
            key: "export",
            label: "导出结果",
            children: (
              <Card title="导出结果" className="panel-card">
                <Space direction="vertical" size={16}>
                  <Alert
                    type="info"
                    showIcon
                    message="当前稳定导出仍为已有 Label Studio 关键帧 0/1 mask 导出；CVAT B-line 导出接口为 spike placeholder。"
                  />
                  <Button type="primary" onClick={() => void handleExport()} loading={exporting}>
                    导出 B-line 关键帧数据集
                  </Button>
                </Space>
              </Card>
            ),
          },
        ]}
      />
    </Space>
  );
}
