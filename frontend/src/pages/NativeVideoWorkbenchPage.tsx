import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AimOutlined, ArrowLeftOutlined, PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, App, Button, Card, Descriptions, Empty, Radio, Space, Tag, Typography } from "antd";
import { useNavigate, useParams } from "react-router-dom";

import {
  buildMockPredictFrameResponse,
  decodeRleMask,
  type MedSamBackendMode,
  type MedSamPointPrompt,
  type MedSamPredictFrameResponse,
  type MedSamPrompt,
  predictFrameWithRealService,
} from "../api/medsam2";
import { getVideoDataset, listDatasetVideos } from "../api/videos";
import type { VideoDatasetSummary, VideoItem } from "../types/api";

interface NativeObject {
  object_id: string;
  label: string;
  color: string;
}

interface SavedWorkbenchState {
  session_id: string;
  current_frame: number;
  active_object_id: string | null;
  objects: NativeObject[];
  prompts: Record<string, MedSamPrompt[]>;
  masks: Record<string, MedSamPredictFrameResponse>;
}

const objectColors = ["#14b8a6", "#f97316", "#2563eb", "#db2777", "#65a30d"];

function makeSessionId(videoId: string) {
  return `native-${videoId}-${Date.now().toString(36)}`;
}

function stateKey(datasetId: string, videoId: string) {
  return `native-video-workbench:v1:${datasetId}:${videoId}`;
}

function emptyState(videoId: string): SavedWorkbenchState {
  return {
    session_id: makeSessionId(videoId),
    current_frame: 0,
    active_object_id: null,
    objects: [],
    prompts: {},
    masks: {},
  };
}

function loadSavedState(datasetId: string, videoId: string): SavedWorkbenchState {
  try {
    const rawValue = localStorage.getItem(stateKey(datasetId, videoId));
    if (!rawValue) {
      return emptyState(videoId);
    }
    const parsed = JSON.parse(rawValue) as SavedWorkbenchState;
    return {
      ...emptyState(videoId),
      ...parsed,
      objects: Array.isArray(parsed.objects) ? parsed.objects : [],
      prompts: parsed.prompts || {},
      masks: parsed.masks || {},
    };
  } catch {
    return emptyState(videoId);
  }
}

function saveState(datasetId: string, videoId: string, state: SavedWorkbenchState) {
  localStorage.setItem(stateKey(datasetId, videoId), JSON.stringify(state));
}

function formatFrameTime(frameIndex: number, fps?: number | null) {
  if (!fps) {
    return "0.00s";
  }
  return `${(frameIndex / fps).toFixed(2)}s`;
}

export function NativeVideoWorkbenchPage() {
  const { datasetId, videoId } = useParams<{ datasetId: string; videoId: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [summary, setSummary] = useState<VideoDatasetSummary | null>(null);
  const [video, setVideo] = useState<VideoItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendMode, setBackendMode] = useState<MedSamBackendMode>("mock");
  const [predicting, setPredicting] = useState(false);
  const [state, setState] = useState<SavedWorkbenchState | null>(null);

  const activeObject = useMemo(
    () => state?.objects.find((item) => item.object_id === state.active_object_id) || null,
    [state],
  );
  const activeMask = activeObject && state ? state.masks[activeObject.object_id] : null;
  const activePrompts = activeObject && state ? state.prompts[activeObject.object_id] || [] : [];
  const positivePrompts = activePrompts.filter((prompt): prompt is MedSamPointPrompt => prompt.type === "point" && prompt.label === 1);

  const loadData = useCallback(async () => {
    if (!datasetId || !videoId) {
      return;
    }
    setLoading(true);
    try {
      const [datasetResponse, videosResponse] = await Promise.all([
        getVideoDataset(datasetId),
        listDatasetVideos(datasetId),
      ]);
      const foundVideo = videosResponse.videos.find((item) => item.id === videoId) || null;
      setSummary(datasetResponse);
      setVideo(foundVideo);
      setState(loadSavedState(datasetId, videoId));
      if (!foundVideo) {
        message.error("未找到当前视频。");
      }
    } catch (error) {
      setSummary(null);
      setVideo(null);
      setState(null);
      message.error(error instanceof Error ? error.message : "加载原生视频工作台失败。");
    } finally {
      setLoading(false);
    }
  }, [datasetId, message, videoId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (!datasetId || !videoId || !state) {
      return;
    }
    saveState(datasetId, videoId, state);
  }, [datasetId, state, videoId]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !video?.width || !video?.height) {
      return;
    }
    canvas.width = video.width;
    canvas.height = video.height;
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (!activeMask || !activeObject) {
      return;
    }
    const decoded = decodeRleMask(activeMask.mask);
    const imageData = context.createImageData(decoded.width, decoded.height);
    const color = activeObject.color;
    const red = parseInt(color.slice(1, 3), 16);
    const green = parseInt(color.slice(3, 5), 16);
    const blue = parseInt(color.slice(5, 7), 16);
    decoded.bits.forEach((bit, index) => {
      if (!bit) {
        return;
      }
      const offset = index * 4;
      imageData.data[offset] = red;
      imageData.data[offset + 1] = green;
      imageData.data[offset + 2] = blue;
      imageData.data[offset + 3] = 112;
    });
    context.putImageData(imageData, 0, 0);
  }, [activeMask, activeObject, video?.height, video?.width]);

  const updateFrameFromVideo = () => {
    if (!videoRef.current || !video?.fps || !state) {
      return;
    }
    const nextFrame = Math.min(Math.max(Math.round(videoRef.current.currentTime * video.fps), 0), Math.max((video.frame_count || 1) - 1, 0));
    if (nextFrame !== state.current_frame) {
      setState({ ...state, current_frame: nextFrame });
    }
  };

  const createObject = () => {
    if (!state) {
      return;
    }
    const nextIndex = state.objects.length + 1;
    const object: NativeObject = {
      object_id: `obj-${String(nextIndex).padStart(3, "0")}`,
      label: `目标 ${nextIndex}`,
      color: objectColors[(nextIndex - 1) % objectColors.length],
    };
    setState({
      ...state,
      active_object_id: object.object_id,
      objects: [...state.objects, object],
      prompts: { ...state.prompts, [object.object_id]: [] },
    });
    message.success(`已创建 ${object.label}`);
  };

  const resetLocalSession = () => {
    if (!datasetId || !videoId) {
      return;
    }
    const nextState = emptyState(videoId);
    setState(nextState);
    saveState(datasetId, videoId, nextState);
    message.success("已重置本地原生标注会话。");
  };

  const handleCanvasClick = async (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!datasetId || !video || !state || !activeObject) {
      message.warning("请先创建并选择一个目标。");
      return;
    }
    if (!video.width || !video.height) {
      message.warning("当前视频缺少宽高元数据，暂不能生成 Mask。");
      return;
    }
    const width = video.width;
    const height = video.height;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.round(((event.clientX - rect.left) / rect.width) * width);
    const y = Math.round(((event.clientY - rect.top) / rect.height) * height);
    const pointPrompt: MedSamPointPrompt = {
      type: "point",
      label: 1,
      point: [Math.max(0, Math.min(width - 1, x)), Math.max(0, Math.min(height - 1, y))],
    };
    const prompts = [...(state.prompts[activeObject.object_id] || []), pointPrompt];
    const request = {
      task_id: datasetId,
      video_id: video.id,
      session_id: state.session_id,
      video_ref: video.file_url,
      frame_index: state.current_frame,
      object_id: activeObject.object_id,
      prompts,
    };

    setPredicting(true);
    try {
      const response =
        backendMode === "mock"
          ? buildMockPredictFrameResponse(request, width, height)
          : await predictFrameWithRealService(request);
      setState({
        ...state,
        prompts: { ...state.prompts, [activeObject.object_id]: prompts },
        masks: { ...state.masks, [activeObject.object_id]: response },
      });
      message.success(backendMode === "mock" ? "Mock Mask 已生成。" : "MedSAM2 Mask 已生成。");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "生成 Mask 失败。");
    } finally {
      setPredicting(false);
    }
  };

  if (!datasetId || !videoId) {
    return <Empty description="缺少视频任务参数。" />;
  }

  if (!loading && !video) {
    return (
      <Empty description="未找到当前视频。" image={Empty.PRESENTED_IMAGE_SIMPLE}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/tasks/video/${datasetId}`)}>
          返回视频任务
        </Button>
      </Empty>
    );
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card className="hero-card" loading={loading}>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Space wrap align="center">
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/tasks/video/${datasetId}`)}>
              返回视频任务
            </Button>
            <Tag color="blue">平台原生视频工作台</Tag>
            <Tag color={backendMode === "mock" ? "cyan" : "purple"}>{backendMode === "mock" ? "Mock" : "Real"}</Tag>
          </Space>
          <Typography.Title level={2} className="detail-title">
            {video?.filename || "原生视频标注工作台"}
          </Typography.Title>
          <Typography.Paragraph className="hero-description">
            当前工作台在平台内完成视频加载、目标创建、正点提示和 Mask 叠加。刷新后会恢复本地最小会话状态。
          </Typography.Paragraph>
        </Space>
      </Card>

      <div className="native-workbench-grid">
        <Card title="视频与 Mask" className="panel-card native-video-card">
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <div
              className="native-video-stage"
              style={video?.width && video.height ? { aspectRatio: `${video.width} / ${video.height}` } : undefined}
            >
              {video ? (
                <>
                  <video
                    ref={videoRef}
                    src={video.file_url}
                    controls
                    className="native-video-element"
                    onTimeUpdate={updateFrameFromVideo}
                    onSeeked={updateFrameFromVideo}
                    onLoadedMetadata={updateFrameFromVideo}
                  />
                  <canvas
                    ref={canvasRef}
                    className="native-mask-overlay"
                    onClick={(event) => void handleCanvasClick(event)}
                    title="点击添加正点提示"
                  />
                  {positivePrompts.map((prompt, index) => (
                    <span
                      key={`${prompt.point[0]}-${prompt.point[1]}-${index}`}
                      className="native-positive-point"
                      style={{
                        left: `${(prompt.point[0] / Math.max(video.width || 1, 1)) * 100}%`,
                        top: `${(prompt.point[1] / Math.max(video.height || 1, 1)) * 100}%`,
                        borderColor: activeObject?.color || "#14b8a6",
                      }}
                    />
                  ))}
                </>
              ) : null}
            </div>
            <Alert
              type={activeObject ? "info" : "warning"}
              showIcon
              message={activeObject ? "点击视频画面添加正点提示。" : "请先创建一个目标，再在目标内部点击正点。"}
            />
          </Space>
        </Card>

        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card title="交互控制" className="panel-card">
            <Space direction="vertical" size={14} style={{ width: "100%" }}>
              <Radio.Group value={backendMode} onChange={(event) => setBackendMode(event.target.value)}>
                <Radio.Button value="mock">Mock</Radio.Button>
                <Radio.Button value="real">Real</Radio.Button>
              </Radio.Group>
              <Button type="primary" icon={<PlusOutlined />} onClick={createObject} block>
                创建目标
              </Button>
              <Button icon={<ReloadOutlined />} onClick={resetLocalSession} block>
                重置本地会话
              </Button>
              <Button icon={<AimOutlined />} loading={predicting} disabled block>
                正点交互模式
              </Button>
            </Space>
          </Card>

          <Card title="会话状态" className="panel-card">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="dataset_id">{datasetId}</Descriptions.Item>
              <Descriptions.Item label="video_id">{videoId}</Descriptions.Item>
              <Descriptions.Item label="session_id">{state?.session_id || "-"}</Descriptions.Item>
              <Descriptions.Item label="当前帧">{state?.current_frame ?? 0}</Descriptions.Item>
              <Descriptions.Item label="时间">{formatFrameTime(state?.current_frame || 0, video?.fps)}</Descriptions.Item>
              <Descriptions.Item label="目标数">{state?.objects.length || 0}</Descriptions.Item>
              <Descriptions.Item label="正点数">{positivePrompts.length}</Descriptions.Item>
              <Descriptions.Item label="Mask">{activeMask ? `${activeMask.backend} / score ${activeMask.score}` : "未生成"}</Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="目标列表" className="panel-card">
            {state && state.objects.length > 0 ? (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                {state.objects.map((object) => (
                  <Button
                    key={object.object_id}
                    type={state.active_object_id === object.object_id ? "primary" : "default"}
                    onClick={() => setState({ ...state, active_object_id: object.object_id })}
                    block
                  >
                    <span className="native-object-swatch" style={{ background: object.color }} />
                    {object.label} · {object.object_id}
                  </Button>
                ))}
              </Space>
            ) : (
              <Empty description="暂无目标" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>

          <Card title="视频信息" className="panel-card">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="任务">{summary?.dataset_name || "-"}</Descriptions.Item>
              <Descriptions.Item label="尺寸">{video ? `${video.width || "-"}x${video.height || "-"}` : "-"}</Descriptions.Item>
              <Descriptions.Item label="帧数">{video?.frame_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="FPS">{video?.fps ?? "-"}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Space>
      </div>
    </Space>
  );
}
