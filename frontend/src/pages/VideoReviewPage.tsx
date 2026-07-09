import React from "react";
import { Alert, App, Button, Card, Col, Descriptions, Empty, Form, Image, Input, Row, Select, Space, Switch, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { extractVideoKeyframes, listDatasetVideos, listVideoKeyframes, updateVideoReview } from "../api/videos";
import { StatusTag } from "../components/StatusTag";
import type { BLineGrade, KeyFrame, KeyFrameReason, VideoItem, VideoQuality } from "../types/api";

interface ReviewFormValues {
  quality: VideoQuality;
  bline_grade: BLineGrade;
  uncertain_flag: boolean;
  include_in_training: boolean;
  comment?: string;
}

interface ExtractFormValues {
  frame_indices_input?: string;
  interval_input?: string;
  selection_reason: KeyFrameReason;
}

const qualityOptions = ["good", "usable", "poor", "unknown"].map((value) => ({ label: value, value }));
const gradeOptions = ["0", "1-2", "3+", "confluent", "unknown"].map((value) => ({ label: value, value }));
const reasonOptions: { label: string; value: KeyFrameReason }[] = [
  { label: "first_clear", value: "first_clear" },
  { label: "most_obvious", value: "most_obvious" },
  { label: "appear", value: "appear" },
  { label: "disappear", value: "disappear" },
  { label: "count_change", value: "count_change" },
  { label: "interval_sample", value: "interval_sample" },
  { label: "issue_frame", value: "issue_frame" },
  { label: "manual", value: "manual" },
];

function parseFrameIndices(input?: string) {
  if (!input) {
    return [];
  }
  return input
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .map((item) => {
      const value = Number(item);
      if (!Number.isInteger(value) || value < 0) {
        throw new Error(`非法帧号: ${item}`);
      }
      return value;
    });
}

function parsePositiveInteger(input?: string) {
  if (!input || input.trim().length === 0) {
    return undefined;
  }
  const value = Number(input.trim());
  if (!Number.isInteger(value) || value < 1) {
    throw new Error("interval must be a positive integer");
  }
  return value;
}

function formatDuration(value?: number | null) {
  if (value == null) {
    return "-";
  }
  return `${value.toFixed(1)}s`;
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function VideoReviewPage() {
  const { datasetId, videoId } = useParams<{ datasetId: string; videoId: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [reviewForm] = Form.useForm<ReviewFormValues>();
  const [extractForm] = Form.useForm<ExtractFormValues>();
  const [video, setVideo] = useState<VideoItem | null>(null);
  const [keyframes, setKeyframes] = useState<KeyFrame[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingReview, setSavingReview] = useState(false);
  const [extracting, setExtracting] = useState(false);

  const loadPageData = async (currentDatasetId: string, currentVideoId: string) => {
    setLoading(true);
    try {
      const [videosResponse, keyframesResponse] = await Promise.all([
        listDatasetVideos(currentDatasetId),
        listVideoKeyframes(currentVideoId),
      ]);
      const foundVideo = videosResponse.videos.find((item) => item.id === currentVideoId) || null;
      setVideo(foundVideo);
      setKeyframes(keyframesResponse.keyframes);
      if (foundVideo) {
        reviewForm.setFieldsValue({
          quality: foundVideo.quality,
          bline_grade: foundVideo.bline_grade,
          uncertain_flag: foundVideo.uncertain_flag,
          include_in_training: foundVideo.include_in_training,
          comment: foundVideo.review_comment || "",
        });
      }
    } catch (error) {
      setVideo(null);
      setKeyframes([]);
      message.error(error instanceof Error ? error.message : "加载视频审核页面失败。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!datasetId || !videoId) {
      return;
    }
    void loadPageData(datasetId, videoId);
  }, [datasetId, videoId, reviewForm]);

  const handleSaveReview = async () => {
    if (!videoId || !datasetId) {
      return;
    }
    try {
      const values = await reviewForm.validateFields();
      setSavingReview(true);
      await updateVideoReview(videoId, {
        quality: values.quality,
        bline_grade: values.bline_grade,
        uncertain_flag: values.uncertain_flag,
        include_in_training: values.include_in_training,
        comment: values.comment || null,
      });
      message.success("视频 review 已保存。");
      await loadPageData(datasetId, videoId);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存视频 review 失败。");
    } finally {
      setSavingReview(false);
    }
  };

  const handleExtractKeyframes = async () => {
    if (!videoId || !datasetId) {
      return;
    }

    try {
      const values = await extractForm.validateFields();
      const frameIndices = parseFrameIndices(values.frame_indices_input);
      const interval = parsePositiveInteger(values.interval_input);
      if (frameIndices.length === 0 && interval == null) {
        message.warning("请填写 frame_indices 或 interval。");
        return;
      }

      setExtracting(true);
      await extractVideoKeyframes(videoId, {
        frame_indices: frameIndices.length > 0 ? frameIndices : undefined,
        interval,
        reasons: values.selection_reason ? [values.selection_reason] : undefined,
      });
      message.success("关键帧抽取成功。");
      await loadPageData(datasetId, videoId);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "关键帧抽取失败。");
    } finally {
      setExtracting(false);
    }
  };

  const keyframeColumns = useMemo<ColumnsType<KeyFrame>>(
    () => [
      {
        title: "缩略图",
        key: "thumb",
        render: (_, record) => (
          <Image
            src={record.image_url}
            alt={`frame-${record.frame_index}`}
            width={96}
            height={64}
            style={{ objectFit: "cover", borderRadius: 10 }}
          />
        ),
      },
      {
        title: "frame_index",
        dataIndex: "frame_index",
        key: "frame_index",
      },
      {
        title: "timestamp_ms",
        dataIndex: "timestamp_ms",
        key: "timestamp_ms",
      },
      {
        title: "selection_reason",
        dataIndex: "selection_reason",
        key: "selection_reason",
      },
      {
        title: "annotation_status",
        dataIndex: "annotation_status",
        key: "annotation_status",
        render: (value: string) => <Tag>{value}</Tag>,
      },
      {
        title: "review_status",
        dataIndex: "review_status",
        key: "review_status",
        render: (value: string) => <Tag color={value === "accepted" ? "success" : "default"}>{value}</Tag>,
      },
    ],
    [],
  );

  if (!datasetId || !videoId) {
    return <Empty description="缺少视频上下文信息" />;
  }

  if (!loading && !video) {
    return <Empty description="未找到当前视频" />;
  }

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Title level={2} className="detail-title">
            视频审核
          </Typography.Title>
          <Typography.Paragraph className="hero-description">
            当前为肺超声 B 线视频关键帧标注 MVP。医生可先查看完整视频，记录视频质量与 B 线等级，再抽取关键帧进入后续 mask 标注流程。
          </Typography.Paragraph>
          <Space wrap>
            <Button onClick={() => navigate(`/video-datasets/${datasetId}`)}>返回数据集详情</Button>
            <Button onClick={() => void loadPageData(datasetId, videoId)} loading={loading}>
              刷新
            </Button>
            {video ? <StatusTag status={video.status} /> : null}
          </Space>
        </Space>
      </Card>

      <Alert
        type="info"
        showIcon
        message="当前阶段不包含 CVAT、视频 AI 预标注或正式双人仲裁。这里仅完成视频级 review 和关键帧抽取。"
      />

      <Row gutter={[24, 24]} align="stretch">
        <Col xs={24} xl={14}>
          <Card title="视频播放器" className="panel-card" loading={loading}>
            {video ? (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <video className="video-review-player" controls src={video.file_url} preload="metadata" />
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="文件名">{video.filename}</Descriptions.Item>
                  <Descriptions.Item label="患者编号">{video.patient_uid || "-"}</Descriptions.Item>
                  <Descriptions.Item label="肺区">{video.lung_zone || "-"}</Descriptions.Item>
                  <Descriptions.Item label="时长">{formatDuration(video.duration_sec)}</Descriptions.Item>
                  <Descriptions.Item label="FPS">{video.fps ?? "-"}</Descriptions.Item>
                  <Descriptions.Item label="帧数">{video.frame_count ?? "-"}</Descriptions.Item>
                  <Descriptions.Item label="分辨率">{`${video.width ?? "-"} x ${video.height ?? "-"}`}</Descriptions.Item>
                  <Descriptions.Item label="设备 / 探头">{`${video.device || "-"} / ${video.probe || "-"}`}</Descriptions.Item>
                </Descriptions>
                {video.preview_image_url ? (
                  <div className="video-preview-block">
                    <Typography.Text strong>首帧预览</Typography.Text>
                    <Image src={video.preview_image_url} alt={`${video.filename}-preview`} className="video-preview-image" />
                  </div>
                ) : null}
              </Space>
            ) : (
              <Empty description="暂无视频信息" />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card title="视频级 Review" className="panel-card" loading={loading}>
            <Form
              form={reviewForm}
              layout="vertical"
              initialValues={{
                quality: "unknown",
                bline_grade: "unknown",
                uncertain_flag: false,
                include_in_training: true,
                comment: "",
              }}
            >
              <Form.Item label="quality" name="quality" rules={[{ required: true, message: "请选择 quality" }]}>
                <Select options={qualityOptions} />
              </Form.Item>
              <Form.Item label="bline_grade" name="bline_grade" rules={[{ required: true, message: "请选择 bline_grade" }]}>
                <Select options={gradeOptions} />
              </Form.Item>
              <Form.Item label="uncertain_flag" name="uncertain_flag" valuePropName="checked">
                <Switch checkedChildren="是" unCheckedChildren="否" />
              </Form.Item>
              <Form.Item label="include_in_training" name="include_in_training" valuePropName="checked">
                <Switch checkedChildren="纳入" unCheckedChildren="排除" />
              </Form.Item>
              <Form.Item label="comment" name="comment">
                <Input.TextArea rows={4} placeholder="记录质量说明、伪影不确定性或其他补充备注" />
              </Form.Item>
              <Button type="primary" block loading={savingReview} onClick={handleSaveReview}>
                保存视频 Review
              </Button>
            </Form>
            {video?.reviewed_at ? (
              <Typography.Text type="secondary">{`最近保存时间：${formatDateTime(video.reviewed_at)}`}</Typography.Text>
            ) : null}
          </Card>
        </Col>
      </Row>

      <Card title="关键帧抽取" className="panel-card" loading={loading}>
        <Form form={extractForm} layout="vertical" initialValues={{ selection_reason: "manual" }}>
          <Row gutter={[16, 0]}>
            <Col xs={24} xl={10}>
              <Form.Item label="frame_indices" name="frame_indices_input">
                <Input placeholder="例如：0,5,10" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12} xl={6}>
              <Form.Item label="interval" name="interval_input">
                <Input inputMode="numeric" placeholder="例如：4" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12} xl={8}>
              <Form.Item label="selection_reason" name="selection_reason" rules={[{ required: true, message: "请选择 selection_reason" }]}>
                <Select options={reasonOptions} />
              </Form.Item>
            </Col>
          </Row>
          <Space wrap>
            <Button type="primary" loading={extracting} onClick={handleExtractKeyframes}>
              抽取关键帧
            </Button>
            <Typography.Text type="secondary">可填 frame_indices、interval，或两者同时提交。frame_indices 会自动去空格并做非负整数校验。</Typography.Text>
          </Space>
        </Form>
      </Card>

      <Card title="关键帧列表" className="panel-card" extra={<Typography.Text>{`共 ${keyframes.length} 张`}</Typography.Text>}>
        <Table rowKey="id" columns={keyframeColumns} dataSource={keyframes} pagination={{ pageSize: 6, showSizeChanger: false }} scroll={{ x: 920 }} />
        {!loading && keyframes.length === 0 ? <Empty description="尚未抽取关键帧" /> : null}
      </Card>
    </Space>
  );
}
