import React, { useEffect, useMemo, useState } from "react";
import { Alert, App, Button, Card, Descriptions, Empty, Image, Modal, Space, Table, Tabs, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useNavigate, useParams } from "react-router-dom";

import {
  exportCvatBlineTest,
  getCvatAccess,
  getCvatAnnotationSummary,
  getCvatHealth,
  getVideoDataset,
  initDatasetCvat,
  listDatasetVideos,
  syncDatasetCvat,
} from "../api/videos";
import { StatusTag } from "../components/StatusTag";
import type {
  CvatAccessResponse,
  CvatAnnotationSummaryResponse,
  CvatHealthResponse,
  ReviewSummaryItem,
  SplitSummaryItem,
  VideoDatasetSummary,
  VideoItem,
} from "../types/api";

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

function renderCvatSummary(item?: CvatAnnotationSummaryResponse) {
  if (!item) {
    return <Typography.Text type="secondary">未同步</Typography.Text>;
  }
  if (item.error) {
    return <Typography.Text type="warning">{item.error}</Typography.Text>;
  }
  return (
    <Space direction="vertical" size={0}>
      <Typography.Text>{`关键帧 ${item.selected_keyframe_count}，待处理 ${item.pending_frame_count}`}</Typography.Text>
      <Typography.Text>{`positive ${item.positive_frame_count} / negative ${item.negative_frame_count} / uncertain ${item.uncertain_frame_count}`}</Typography.Text>
      <Typography.Text type="secondary">{`Polygon ${item.polygon_count}，Issue 未解决/已解决 ${item.unresolved_issue_count}/${item.resolved_issue_count}`}</Typography.Text>
      <Typography.Text type="secondary">{`CVAT ${item.cvat_task_status || "-"} / ${item.cvat_job_state || "-"} / ${item.cvat_job_stage || "-"}`}</Typography.Text>
    </Space>
  );
}

function cvatBaseUrl(summary: VideoDatasetSummary | null, videos: VideoItem[]) {
  const candidates = [summary?.cvat_project_url, ...videos.map((video) => video.cvat_job_url || video.cvat_task_url)].filter(Boolean) as string[];
  for (const candidate of candidates) {
    try {
      return new URL(candidate).origin;
    } catch {
      // Ignore malformed URLs from older rows and fall back below.
    }
  }
  return "http://localhost:8081";
}

function cvatLoginUrl(summary: VideoDatasetSummary | null, videos: VideoItem[]) {
  return `${cvatBaseUrl(summary, videos)}/auth/login`;
}

export function VideoDatasetDetailPage() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [summary, setSummary] = useState<VideoDatasetSummary | null>(null);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [cvatHealth, setCvatHealth] = useState<CvatHealthResponse | null>(null);
  const [cvatSummaries, setCvatSummaries] = useState<Record<string, CvatAnnotationSummaryResponse>>({});
  const [cvatAccess, setCvatAccess] = useState<Record<string, CvatAccessResponse>>({});
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [initializingCvat, setInitializingCvat] = useState(false);
  const [syncingCvat, setSyncingCvat] = useState(false);
  const [previewVideo, setPreviewVideo] = useState<VideoItem | null>(null);

  const loadData = async (currentDatasetId: string) => {
    setLoading(true);
    try {
      const [summaryResponse, videosResponse] = await Promise.all([
        getVideoDataset(currentDatasetId),
        listDatasetVideos(currentDatasetId),
      ]);
      setSummary(summaryResponse);
      setVideos(videosResponse.videos);
      const shouldLoadCvat = summaryResponse.annotation_backend === "cvat";
      if (!shouldLoadCvat) {
        setCvatHealth(null);
        setCvatSummaries({});
        setCvatAccess({});
        return;
      }

      const healthResponse = await getCvatHealth();
      setCvatHealth(healthResponse);

      const initializedVideos = videosResponse.videos.filter((video) => video.cvat_task_id);
      const summaryEntries = await Promise.all(
        initializedVideos.map(async (video) => {
          try {
            return [video.id, await getCvatAnnotationSummary(video.id)] as const;
          } catch {
            return null;
          }
        }),
      );
      const accessEntries = await Promise.all(
        initializedVideos.map(async (video) => {
          try {
            return [video.id, await getCvatAccess(video.id)] as const;
          } catch {
            return null;
          }
        }),
      );
      setCvatSummaries(Object.fromEntries(summaryEntries.filter((item): item is readonly [string, CvatAnnotationSummaryResponse] => item !== null)));
      setCvatAccess(Object.fromEntries(accessEntries.filter((item): item is readonly [string, CvatAccessResponse] => item !== null)));
    } catch (error) {
      setSummary(null);
      setVideos([]);
      setCvatSummaries({});
      setCvatAccess({});
      message.error(error instanceof Error ? error.message : "加载视频任务详情失败。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (datasetId) {
      void loadData(datasetId);
    }
  }, [datasetId]);

  const isLegacyLabelStudio = summary?.annotation_backend === "label_studio";
  const isCvatFlow = summary?.annotation_backend === "cvat";
  const isNativeFlow = !loading && !isLegacyLabelStudio && !isCvatFlow;
  const canUseCvat = Boolean(cvatHealth?.reachable && cvatHealth.authenticated);
  const initializedCount = videos.filter((video) => cvatAccess[video.id]?.access_ready).length;
  const uninitializedCount = Math.max(videos.length - initializedCount, 0);
  const allInitialized = videos.length > 0 && uninitializedCount === 0;
  const assigneeUsername =
    Object.values(cvatAccess).find((item) => item.assignee_username)?.assignee_username ||
    cvatHealth?.default_assignee_username ||
    cvatHealth?.authenticated_username ||
    "指定 CVAT 账号";

  const handleExport = async () => {
    if (!datasetId) {
      return;
    }
    try {
      setExporting(true);
      const result = await exportCvatBlineTest(datasetId);
      window.open(result.download_url, "_blank", "noopener,noreferrer");
      message.success(`导出完成：有效样本 ${result.total_labeled_count} 帧，跳过 ${result.skipped_count} 帧。`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "导出 CVAT B-line 数据集失败。");
    } finally {
      setExporting(false);
    }
  };

  const handleInitCvat = async () => {
    if (!datasetId) {
      return;
    }
    if (isLegacyLabelStudio) {
      message.warning("该视频任务使用旧版 Label Studio 视频流程，不会自动迁移到 CVAT。");
      return;
    }
    try {
      setInitializingCvat(true);
      const result = await initDatasetCvat(datasetId);
      if (result.warning) {
        message.warning(result.warning);
      }
      if (result.error) {
        message.warning(result.error);
      } else {
        message.success(
          `CVAT 初始化完成：新建 ${result.created_task_count} 个，复用 ${result.reused_task_count} 个，修复 ${result.repaired_task_count} 个，失败 ${result.failed_task_count} 个。`,
        );
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

  const handleOpenCvat = async (record: VideoItem) => {
    if (!record.cvat_job_id) {
      message.warning("该视频还没有 CVAT Job，请先创建 CVAT 标注任务。");
      return;
    }
    const popup = window.open("about:blank", "_blank");
    if (popup) {
      popup.opener = null;
    }
    try {
      const access = await getCvatAccess(record.id);
      setCvatAccess((current) => ({ ...current, [record.id]: access }));
      if (!access.access_ready || !access.job_url) {
        popup?.close();
        message.error(access.warning || "CVAT Job 尚未准备好，暂不能打开。");
        return;
      }
      if (access.warning) {
        message.warning(access.warning);
      }
      if (popup) {
        popup.location.href = access.job_url;
      } else {
        window.open(access.job_url, "_blank", "noopener,noreferrer");
      }
    } catch (error) {
      popup?.close();
      message.error(error instanceof Error ? error.message : "检查 CVAT 访问状态失败。");
    }
  };

  const openCvatLogin = () => {
    window.open(cvatLoginUrl(summary, videos), "_blank", "noopener,noreferrer");
  };

  const aggregate = Object.values(cvatSummaries).reduce(
    (acc, item) => ({
      selected: acc.selected + item.selected_keyframe_count,
      polygons: acc.polygons + item.polygon_count,
      positive: acc.positive + item.positive_frame_count,
      negative: acc.negative + item.negative_frame_count,
      uncertain: acc.uncertain + item.uncertain_frame_count,
      issues: acc.issues + item.issue_count,
      unresolved: acc.unresolved + item.unresolved_issue_count,
      resolved: acc.resolved + item.resolved_issue_count,
    }),
    { selected: 0, polygons: 0, positive: 0, negative: 0, uncertain: 0, issues: 0, unresolved: 0, resolved: 0 },
  );

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
              <Typography.Text type="secondary">{record.lung_zone || "-"}</Typography.Text>
            </Space>
          </Space>
        ),
      },
      {
        title: "基础信息",
        key: "metrics",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{`${formatNumber(record.duration_sec, 1)}s / ${formatNumber(record.fps, 1)} fps`}</Typography.Text>
            <Typography.Text type="secondary">{`${record.frame_count ?? "-"} 帧 / ${record.width ?? "-"}x${record.height ?? "-"}`}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "CVAT",
        key: "cvat",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Tag color={record.cvat_task_id ? "processing" : "default"}>{record.cvat_status || "not_initialized"}</Tag>
            <Typography.Text type="secondary">{record.cvat_task_id ? `task ${record.cvat_task_id}` : "未初始化"}</Typography.Text>
            {record.cvat_job_id ? <Typography.Text type="secondary">{`job ${record.cvat_job_id}`}</Typography.Text> : null}
          </Space>
        ),
      },
      {
        title: "标注与复核",
        key: "cvat_summary",
        render: (_, record) => renderCvatSummary(cvatSummaries[record.id]),
      },
      {
        title: "平台状态",
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
            <Button onClick={() => setPreviewVideo(record)}>预览原视频</Button>
            <Button type="primary" disabled={!canUseCvat || !record.cvat_job_id} onClick={() => void handleOpenCvat(record)}>
              进入 CVAT 标注
            </Button>
          </Space>
        ),
      },
    ],
    [canUseCvat, cvatSummaries],
  );

  const legacyColumns = useMemo<ColumnsType<VideoItem>>(
    () => [
      {
        title: "视频",
        key: "video",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{record.filename}</Typography.Text>
            <Typography.Text type="secondary">{record.patient_uid || "-"}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "基础信息",
        key: "metrics",
        render: (_, record) => <Typography.Text>{`${formatNumber(record.duration_sec, 1)}s / ${formatNumber(record.fps, 1)} fps`}</Typography.Text>,
      },
      {
        title: "关键帧",
        dataIndex: "keyframe_count",
        key: "keyframe_count",
      },
      {
        title: "操作",
        key: "actions",
        render: (_, record) => <Button onClick={() => navigate(`/video-datasets/${record.dataset_id}/videos/${record.id}`)}>进入旧版关键帧页面</Button>,
      },
    ],
    [navigate],
  );

  const nativeColumns = useMemo<ColumnsType<VideoItem>>(
    () => [
      {
        title: "视频",
        key: "video",
        render: (_, record) => (
          <Space size={12}>
            {record.preview_image_url ? (
              <Image src={record.preview_image_url} alt={record.filename} width={84} height={56} style={{ objectFit: "cover", borderRadius: 8 }} preview={false} />
            ) : null}
            <Space direction="vertical" size={0}>
              <Typography.Text strong>{record.filename}</Typography.Text>
              <Typography.Text type="secondary">{record.patient_uid || "未关联患者"}</Typography.Text>
              <Typography.Text type="secondary">{record.lung_zone || "-"}</Typography.Text>
            </Space>
          </Space>
        ),
      },
      {
        title: "基础信息",
        key: "metrics",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{`${formatNumber(record.duration_sec, 1)}s / ${formatNumber(record.fps, 1)} fps`}</Typography.Text>
            <Typography.Text type="secondary">{`${record.frame_count ?? "-"} 帧 / ${record.width ?? "-"}x${record.height ?? "-"}`}</Typography.Text>
          </Space>
        ),
      },
      {
        title: "标注入口",
        key: "native",
        render: () => <Tag color="blue">平台原生工作台</Tag>,
      },
      {
        title: "平台状态",
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
            <Button onClick={() => setPreviewVideo(record)}>预览原视频</Button>
            <Button type="primary" onClick={() => navigate(`/video-datasets/${record.dataset_id}/videos/${record.id}/native-workbench`)}>
              进入原生标注
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
          <Descriptions.Item label="annotation_backend">{summary.annotation_backend || "未设置"}</Descriptions.Item>
          {isCvatFlow ? <Descriptions.Item label="CVAT Project">{summary.cvat_project_id || "-"}</Descriptions.Item> : null}
          <Descriptions.Item label="任务类型">肺超声 B-line 视频分割</Descriptions.Item>
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
      type={canUseCvat ? "success" : "warning"}
      showIcon
      message={canUseCvat ? `CVAT 服务运行正常 · 版本 ${cvatHealth.server_version || "unknown"}` : "CVAT 服务不可用"}
      description={
        cvatHealth.error ||
        `该任务已分配给 CVAT 账号：${assigneeUsername}。首次使用：1. 点击“登录 CVAT”；2. 使用账号 ${assigneeUsername} 登录；3. 登录成功后返回本页；4. 点击“进入 CVAT 标注”。登录密码请使用本地管理员提供的 CVAT 密码。支持问题复核：${cvatHealth.issue_supported ? "是" : "未确认"}。`
      }
      action={<Button onClick={openCvatLogin}>登录 CVAT</Button>}
    />
  ) : null;

  const cvatTaskControls = (
    <Space wrap>
      <Typography.Text>{`总视频 ${videos.length} · 已初始化 ${initializedCount} · 未初始化 ${uninitializedCount}`}</Typography.Text>
      {!allInitialized ? (
        <Button type="primary" onClick={() => void handleInitCvat()} loading={initializingCvat} disabled={!canUseCvat}>
          创建 CVAT 标注任务
        </Button>
      ) : (
        <Tag color="success">全部视频已初始化</Tag>
      )}
      <Button onClick={() => void handleSyncCvat()} loading={syncingCvat} disabled={!canUseCvat || videos.length === 0}>
        同步 CVAT 状态
      </Button>
    </Space>
  );

  const videoTable = (
    <Card title="CVAT 视频标注" className="panel-card" extra={cvatTaskControls}>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {cvatAlert}
        <Table rowKey="id" loading={loading} columns={columns} dataSource={videos} pagination={{ pageSize: 8, showSizeChanger: false }} scroll={{ x: 1500 }} />
        {!loading && videos.length === 0 ? <Empty description="暂无视频数据" /> : null}
      </Space>
    </Card>
  );

  const nativeVideoTable = (
    <Card title="平台原生视频标注" className="panel-card">
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type="success"
          showIcon
          message="新视频任务将进入平台原生工作台，不再创建或跳转 CVAT。"
          description="第一阶段 MVP 支持短视频加载、目标创建、正点提示、Mock Mask 叠加和刷新后的本地最小会话恢复。"
        />
        <Table rowKey="id" loading={loading} columns={nativeColumns} dataSource={videos} pagination={{ pageSize: 8, showSizeChanger: false }} scroll={{ x: 980 }} />
        {!loading && videos.length === 0 ? <Empty description="暂无视频数据" /> : null}
      </Space>
    </Card>
  );

  const statusCard = (
    <Card title="标注与复核状态" className="panel-card">
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          message="平台从 CVAT 同步 Keyframe、FrameDecision、B-line Polygon 和 Issue 状态。"
          description="Issue 的创建、修改和 resolve 仍在 CVAT UI 中完成；平台负责展示状态摘要并在导出时跳过未解决 Issue。"
        />
        <Descriptions column={1} size="small">
          <Descriptions.Item label="已选择关键帧">{aggregate.selected}</Descriptions.Item>
          <Descriptions.Item label="positive / negative / uncertain">{`${aggregate.positive} / ${aggregate.negative} / ${aggregate.uncertain}`}</Descriptions.Item>
          <Descriptions.Item label="Polygon">{aggregate.polygons}</Descriptions.Item>
          <Descriptions.Item label="Issue 未解决 / 已解决">{`${aggregate.unresolved} / ${aggregate.resolved}`}</Descriptions.Item>
          <Descriptions.Item label="最近同步">{formatDateTime(videos.find((video) => video.cvat_annotation_updated_at)?.cvat_annotation_updated_at)}</Descriptions.Item>
        </Descriptions>
        <Button onClick={() => void handleSyncCvat()} loading={syncingCvat} disabled={!canUseCvat}>
          同步 CVAT 状态
        </Button>
      </Space>
    </Card>
  );

  const exportCard = (
    <Card title="导出结果" className="panel-card">
      <Space direction="vertical" size={16}>
        <Alert
          type="info"
          showIcon
          message="CVAT 导出规则：positive + Polygon + 无未解决 Issue 导出 0/1 mask；negative 导出全 0 mask；uncertain、pending、冲突或未解决 Issue 写入 skipped.json。"
        />
        <Button type="primary" onClick={() => void handleExport()} loading={exporting} disabled={!canUseCvat || isLegacyLabelStudio}>
          导出 CVAT B-line 数据集
        </Button>
      </Space>
    </Card>
  );

  const legacyFlowCard = (
    <Card title="旧版 Label Studio 视频流程" className="panel-card">
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type="warning"
          showIcon
          message="这是旧版 Label Studio 关键帧视频流程。"
          description="该流程保留兼容，不会自动进入 CVAT，也不会显示 CVAT 初始化、同步或导出按钮。新视频任务请使用平台原生视频工作台。"
        />
        <Table rowKey="id" loading={loading} columns={legacyColumns} dataSource={videos} pagination={{ pageSize: 8, showSizeChanger: false }} />
      </Space>
    </Card>
  );

  if (!datasetId) {
    return <Empty description="未找到数据集 ID" />;
  }

  let tabItems = [
    { key: "overview", label: "任务概览", children: summaryCard },
    { key: "legacy-label-studio", label: "旧版 Label Studio 视频流程", children: legacyFlowCard },
  ];
  if (isNativeFlow) {
    tabItems = [
      { key: "overview", label: "任务概览", children: summaryCard },
      { key: "native-video", label: "原生视频标注", children: nativeVideoTable },
    ];
  } else if (isCvatFlow) {
    tabItems = [
      { key: "overview", label: "任务概览", children: summaryCard },
      { key: "cvat-video", label: "CVAT 历史兼容", children: videoTable },
      { key: "cvat-status", label: "标注与复核状态", children: statusCard },
      { key: "export", label: "导出结果", children: exportCard },
    ];
  }

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Typography.Title level={2} className="detail-title">
            {summary?.dataset_name || "视频任务详情"}
          </Typography.Title>
          <Typography.Paragraph className="hero-description">
            当前视频业务流程：上传视频、进入平台原生工作台、创建目标、使用点提示生成 Mask，并在后续阶段接入 MedSAM2 推理与统一导出。
          </Typography.Paragraph>
          {isCvatFlow ? (
            <Alert
              type="info"
              showIcon
              message={`该任务已分配给 CVAT 账号：${assigneeUsername}`}
              description={`首次使用：1. 点击“登录 CVAT”；2. 使用账号 ${assigneeUsername} 登录；3. 登录成功后返回本页；4. 点击“进入 CVAT 标注”。登录密码请使用本地管理员提供的 CVAT 密码。不要自行注册其他账号；使用其他 CVAT 账号登录时，可能看不到该任务。`}
            />
          ) : null}
          <Space wrap>
            <Button onClick={() => navigate("/tasks")}>返回任务列表</Button>
            <Button onClick={() => navigate("/")}>上传新数据</Button>
            <Button onClick={() => void loadData(datasetId)} loading={loading}>
              刷新
            </Button>
          </Space>
        </Space>
      </Card>

      <Tabs items={tabItems} />

      <Modal title={previewVideo?.filename || "预览原视频"} open={Boolean(previewVideo)} footer={null} onCancel={() => setPreviewVideo(null)} width={900} destroyOnClose>
        {previewVideo ? <video src={previewVideo.file_url} controls style={{ width: "100%", borderRadius: 12, background: "#111" }} /> : null}
      </Modal>
    </Space>
  );
}
