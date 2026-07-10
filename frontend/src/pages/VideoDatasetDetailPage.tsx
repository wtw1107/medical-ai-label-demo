import React from "react";
import { Alert, App, Button, Card, Descriptions, Empty, Image, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { exportBlineKeyframes, getVideoDataset, listDatasetVideos } from "../api/videos";
import { StatusTag } from "../components/StatusTag";
import type { ReviewSummaryItem, SplitSummaryItem, VideoDatasetSummary, VideoItem } from "../types/api";

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
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(date);
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
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const loadData = async (currentDatasetId: string) => {
    setLoading(true);
    try {
      const [summaryResponse, videosResponse] = await Promise.all([
        getVideoDataset(currentDatasetId),
        listDatasetVideos(currentDatasetId),
      ]);
      setSummary(summaryResponse);
      setVideos(videosResponse.videos);
    } catch (error) {
      setSummary(null);
      setVideos([]);
      message.error(error instanceof Error ? error.message : "加载视频数据集失败。");
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
      message.success(`导出完成：已标注 ${result.total_labeled_count} 张，跳过 ${result.skipped_count} 张。`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "导出 B-line 关键帧数据集失败。");
    } finally {
      setExporting(false);
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
              <Image src={record.preview_image_url} alt={record.filename} width={84} height={56} style={{ objectFit: "cover", borderRadius: 10 }} preview={false} />
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
        render: (_, record) => (
          <Button type="primary" onClick={() => navigate(`/video-datasets/${record.dataset_id}/videos/${record.id}`)}>
            进入视频审核
          </Button>
        ),
      },
    ],
    [navigate],
  );

  if (!datasetId) {
    return <Empty description="未找到数据集 ID" />;
  }

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Title level={2} className="detail-title">
            {summary?.dataset_name || "视频数据集详情"}
          </Typography.Title>
          <Typography.Paragraph className="hero-description">
            当前为肺超声 B 线视频审核与关键帧抽取 MVP。可先查看视频摘要，再进入单个视频完成 review 和记帧。
          </Typography.Paragraph>
          <Space wrap>
            <Button onClick={() => navigate("/video-datasets/new")}>上传新视频数据集</Button>
            <Button onClick={() => void loadData(datasetId)} loading={loading}>
              刷新
            </Button>
            <Button type="primary" onClick={() => void handleExport()} loading={exporting}>
              导出 B-line 关键帧数据集
            </Button>
          </Space>
        </Space>
      </Card>

      <Card title="数据集摘要" className="panel-card" loading={loading}>
        {summary ? (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="dataset_id">{summary.dataset_id}</Descriptions.Item>
            <Descriptions.Item label="data_type">{summary.data_type}</Descriptions.Item>
            <Descriptions.Item label="视频数">{summary.video_count}</Descriptions.Item>
            <Descriptions.Item label="患者数">{summary.patient_count}</Descriptions.Item>
            <Descriptions.Item label="关键帧总数">{summary.keyframe_count}</Descriptions.Item>
            <Descriptions.Item label="split 摘要">{renderSplitSummary(summary.split_summary)}</Descriptions.Item>
            <Descriptions.Item label="review 摘要">{renderReviewSummary(summary.review_status_summary)}</Descriptions.Item>
          </Descriptions>
        ) : (
          <Empty description="暂无数据集摘要" />
        )}
      </Card>

      <Card title="视频列表" className="panel-card" extra={<Typography.Text>{`共 ${videos.length} 个视频`}</Typography.Text>}>
        <Alert
          type="info"
          showIcon
          message="导出仅包含已标注关键帧，mask 为 0/1 binary PNG，并附带 manifest.json、manifest.csv、skipped.json 和 README.txt。"
          style={{ marginBottom: 16 }}
        />
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={videos}
          pagination={{ pageSize: 8, showSizeChanger: false }}
          scroll={{ x: 1200 }}
        />
        {!loading && videos.length === 0 ? <Empty description="暂无视频数据" /> : null}
        {!loading && videos.length > 0 ? (
          <Typography.Text type="secondary">最近审核时间会在进入单个视频页保存 review 后更新。</Typography.Text>
        ) : null}
        {videos.some((video) => video.reviewed_at) ? (
          <Typography.Text type="secondary">{`最近一条审核时间：${formatDateTime(videos.find((video) => video.reviewed_at)?.reviewed_at)}`}</Typography.Text>
        ) : null}
      </Card>
    </Space>
  );
}
