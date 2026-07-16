import React, { useEffect, useMemo, useState } from "react";
import { InboxOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Radio,
  Row,
  Select,
  Space,
  Steps,
  Switch,
  Table,
  Typography,
  Upload,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { RcFile, UploadFile } from "antd/es/upload/interface";
import { useNavigate } from "react-router-dom";

import { uploadDataset } from "../api/datasets";
import { createTask } from "../api/tasks";
import { getCvatHealth, uploadVideoDataset } from "../api/videos";
import type { CvatHealthResponse, DatasetUploadResponse, TaskType, VideoDatasetUploadResponse, VideoUploadMetadata } from "../types/api";

type DetectedDataType = "image" | "video" | "mixed" | "unknown";
type ImageTaskType = "bbox" | "polygon" | "bbox_polygon";

interface UploadFormValues {
  datasetName: string;
  datasetDescription?: string;
  taskName?: string;
  taskType: TaskType;
  labelName?: string;
  detModelId?: string;
  segModelId?: string;
  requireHumanConfirm: boolean;
}

type VideoMetadataRow = VideoUploadMetadata & { key: string };

const imageExtensions = new Set(["jpg", "jpeg", "png", "bmp", "tif", "tiff", "zip"]);
const videoExtensions = new Set(["mp4", "avi", "mov", "mkv"]);
const allAcceptedExtensions = [
  ".jpg",
  ".jpeg",
  ".png",
  ".bmp",
  ".tif",
  ".tiff",
  ".zip",
  ".mp4",
  ".avi",
  ".mov",
  ".mkv",
].join(",");

function getExtension(filename: string) {
  const parts = filename.toLowerCase().split(".");
  return parts.length > 1 ? parts[parts.length - 1] || "" : "";
}

function detectDataType(files: UploadFile[]): DetectedDataType {
  if (files.length === 0) {
    return "unknown";
  }

  const types = new Set<DetectedDataType>();
  for (const file of files) {
    const extension = getExtension(file.name);
    if (imageExtensions.has(extension)) {
      types.add("image");
    } else if (videoExtensions.has(extension)) {
      types.add("video");
    } else {
      types.add("unknown");
    }
  }

  if (types.size > 1) {
    return "mixed";
  }
  return [...types][0] || "unknown";
}

function getFiles(fileList: UploadFile[]) {
  return fileList
    .map((item) => item.originFileObj)
    .filter((item): item is RcFile => item instanceof File);
}

function makeMetadataRow(file: UploadFile, existing?: VideoMetadataRow): VideoMetadataRow {
  return {
    key: file.uid,
    filename: file.name,
    patient_uid: existing?.patient_uid || "",
    lung_zone: existing?.lung_zone || "",
    probe: existing?.probe || "",
    device: existing?.device || "",
    depth: existing?.depth || "",
    orientation: existing?.orientation || "",
    deid_status: existing?.deid_status || "unknown",
  };
}

export function UploadPage() {
  const [form] = Form.useForm<UploadFormValues>();
  const [batchForm] = Form.useForm<Partial<VideoUploadMetadata>>();
  const navigate = useNavigate();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [videoRows, setVideoRows] = useState<VideoMetadataRow[]>([]);
  const [selectedVideoRowKeys, setSelectedVideoRowKeys] = useState<React.Key[]>([]);
  const [imageUploadResult, setImageUploadResult] = useState<DatasetUploadResponse | null>(null);
  const [videoUploadResult, setVideoUploadResult] = useState<VideoDatasetUploadResponse | null>(null);
  const [cvatHealth, setCvatHealth] = useState<CvatHealthResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const detectedType = useMemo(() => detectDataType(fileList), [fileList]);
  const selectedTaskType = Form.useWatch("taskType", form) || "bbox_polygon";
  const isVideo = detectedType === "video";
  const isImage = detectedType === "image" || detectedType === "unknown";

  useEffect(() => {
    if (detectedType === "video") {
      form.setFieldsValue({ taskType: "video_bline_segmentation" });
      setVideoRows((currentRows) =>
        fileList.map((file) => makeMetadataRow(file, currentRows.find((row) => row.key === file.uid))),
      );
      return;
    }
    setVideoRows([]);
    setSelectedVideoRowKeys([]);
    if (detectedType === "image" && form.getFieldValue("taskType") === "video_bline_segmentation") {
      form.setFieldsValue({ taskType: "bbox_polygon" });
    }
  }, [detectedType, fileList, form]);

  useEffect(() => {
    if (detectedType !== "video") {
      return;
    }
    void getCvatHealth()
      .then(setCvatHealth)
      .catch(() => setCvatHealth(null));
  }, [detectedType]);

  const updateVideoRow = (key: string, patch: Partial<VideoMetadataRow>) => {
    setVideoRows((rows) => rows.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  };

  const applyBatch = (mode: "selected" | "all") => {
    const values = batchForm.getFieldsValue();
    const patch = Object.fromEntries(
      Object.entries(values).filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== ""),
    ) as Partial<VideoMetadataRow>;
    if (Object.keys(patch).length === 0) {
      message.warning("请先填写要批量应用的视频元数据。");
      return;
    }
    const selected = new Set(selectedVideoRowKeys.map(String));
    if (mode === "selected" && selected.size === 0) {
      message.warning("请先选择要批量填充的视频行。");
      return;
    }
    setVideoRows((rows) =>
      rows.map((row) => (mode === "all" || selected.has(row.key) ? { ...row, ...patch } : row)),
    );
    message.success(mode === "all" ? "已应用到全部视频。" : "已应用到选中视频。");
  };

  const validateVideoMetadata = () => {
    for (const row of videoRows) {
      if (!row.patient_uid.trim()) {
        message.error(`请填写 ${row.filename} 的 patient_uid。`);
        return false;
      }
      if (!row.lung_zone.trim()) {
        message.error(`请填写 ${row.filename} 的 lung_zone。`);
        return false;
      }
    }
    return true;
  };

  const handleSubmit = async () => {
    try {
      if (fileList.length === 0) {
        message.warning("请先选择至少一个图片、ZIP 或视频文件。");
        return;
      }
      if (detectedType === "mixed") {
        message.error("同一个数据集只能包含一种数据类型，请分开上传图片和视频。");
        return;
      }
      if (detectedType === "unknown") {
        message.error("暂不支持所选文件类型，请上传图片、ZIP 或 mp4/avi/mov/mkv 视频。");
        return;
      }

      const values = await form.validateFields();
      const files = getFiles(fileList);
      if (files.length === 0) {
        message.error("未读取到可上传的文件，请重新选择。");
        return;
      }

      setSubmitting(true);
      setImageUploadResult(null);
      setVideoUploadResult(null);

      if (detectedType === "video") {
        if (!validateVideoMetadata()) {
          return;
        }
        const result = await uploadVideoDataset({
          dataset_name: values.datasetName.trim(),
          annotation_backend: cvatHealth?.reachable && cvatHealth.authenticated ? "cvat" : "label_studio",
          metadata: videoRows.map(({ key: _key, ...row }) => ({
            ...row,
            patient_uid: row.patient_uid.trim(),
            lung_zone: row.lung_zone.trim(),
          })),
          files,
        });
        setVideoUploadResult(result);
        message.success("视频数据集已上传，正在进入视频任务详情。");
        navigate(`/tasks/video/${result.dataset_id}`);
        return;
      }

      const dataset = await uploadDataset({
        name: values.datasetName.trim(),
        description: values.datasetDescription?.trim(),
        files,
      });
      setImageUploadResult(dataset);

      const task = await createTask({
        dataset_id: dataset.dataset_id,
        name: values.taskName?.trim() || values.datasetName.trim(),
        task_type: values.taskType as ImageTaskType,
        label_name: values.labelName?.trim() || "病灶",
        det_model_id: values.detModelId || null,
        seg_model_id: values.segModelId || null,
        require_human_confirm: values.requireHumanConfirm,
      });

      message.success("图片标注任务已创建，正在进入任务详情。");
      navigate(`/tasks/${task.task_id}`);
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const typeMessage = useMemo(() => {
    if (detectedType === "mixed") {
      return <Alert type="error" showIcon message="同一个数据集只能包含一种数据类型，请分开上传图片和视频。" />;
    }
    if (detectedType === "video") {
      return (
        <Alert
          type="info"
          showIcon
          message="已识别为视频数据集"
          description="当前视频任务类型固定为肺超声 B-line 视频关键帧分割。请为每个视频单独填写 patient_uid 和 lung_zone。"
        />
      );
    }
    if (detectedType === "image") {
      return <Alert type="info" showIcon message="已识别为图片数据集" description="可创建 bbox、polygon 或 bbox + polygon 图片标注任务。" />;
    }
    return (
      <Alert
        type="info"
        showIcon
        message="请选择同一种数据类型的文件"
        description="支持 jpg/jpeg/png/bmp/tif/tiff/zip 图片数据，以及 mp4/avi/mov/mkv 视频数据。"
      />
    );
  }, [detectedType]);

  const metadataColumns = useMemo<ColumnsType<VideoMetadataRow>>(
    () => [
      {
        title: "filename",
        dataIndex: "filename",
        width: 220,
        fixed: "left",
      },
      {
        title: "patient_uid",
        dataIndex: "patient_uid",
        width: 180,
        render: (_, row) => (
          <Input
            value={row.patient_uid}
            placeholder="脱敏患者 UID"
            onChange={(event) => updateVideoRow(row.key, { patient_uid: event.target.value })}
          />
        ),
      },
      {
        title: "lung_zone",
        dataIndex: "lung_zone",
        width: 150,
        render: (_, row) => (
          <Input value={row.lung_zone} placeholder="R1 / L2" onChange={(event) => updateVideoRow(row.key, { lung_zone: event.target.value })} />
        ),
      },
      {
        title: "probe",
        dataIndex: "probe",
        width: 140,
        render: (_, row) => <Input value={row.probe || ""} onChange={(event) => updateVideoRow(row.key, { probe: event.target.value })} />,
      },
      {
        title: "device",
        dataIndex: "device",
        width: 150,
        render: (_, row) => <Input value={row.device || ""} onChange={(event) => updateVideoRow(row.key, { device: event.target.value })} />,
      },
      {
        title: "depth",
        dataIndex: "depth",
        width: 120,
        render: (_, row) => <Input value={row.depth || ""} onChange={(event) => updateVideoRow(row.key, { depth: event.target.value })} />,
      },
      {
        title: "orientation",
        dataIndex: "orientation",
        width: 160,
        render: (_, row) => (
          <Input value={row.orientation || ""} onChange={(event) => updateVideoRow(row.key, { orientation: event.target.value })} />
        ),
      },
      {
        title: "deid_status",
        dataIndex: "deid_status",
        width: 150,
        render: (_, row) => (
          <Select
            value={row.deid_status || "unknown"}
            style={{ width: "100%" }}
            onChange={(value) => updateVideoRow(row.key, { deid_status: value })}
            options={[
              { label: "unknown", value: "unknown" },
              { label: "passed", value: "passed" },
              { label: "failed", value: "failed" },
              { label: "needs_review", value: "needs_review" },
            ]}
          />
        ),
      },
    ],
    [],
  );

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={15}>
            <Typography.Title className="hero-title">统一上传与任务创建</Typography.Title>
            <Typography.Paragraph className="hero-description">
              从同一个入口上传医学图片或肺超声 cine-loop 视频。平台会按文件类型显示可用任务，并进入对应的图片或视频标注流程。
            </Typography.Paragraph>
          </Col>
          <Col xs={24} xl={9}>
            <Steps
              current={1}
              direction="vertical"
              items={[
                { title: "上传图片或视频" },
                { title: "按数据类型选择任务" },
                { title: "进入任务详情继续标注" },
              ]}
            />
          </Col>
        </Row>
      </Card>

      <Form
        form={form}
        layout="vertical"
        initialValues={{
          taskType: "bbox_polygon",
          labelName: "病灶",
          detModelId: "mock_detection",
          segModelId: "mock_segmentation",
          requireHumanConfirm: true,
        }}
      >
        <Row gutter={[24, 24]}>
          <Col xs={24} xl={14}>
            <Card title="上传数据集" className="panel-card">
              <Form.Item
                label="数据集名称"
                name="datasetName"
                rules={[
                  { required: true, message: "请输入数据集名称" },
                  { whitespace: true, message: "数据集名称不能为空白" },
                ]}
              >
                <Input placeholder="例如：肺部病灶样例集 / B-line cine-loop 样例集" size="large" />
              </Form.Item>
              <Form.Item label="数据集说明" name="datasetDescription">
                <Input.TextArea rows={3} placeholder="可选，描述数据来源、用途或采集条件" />
              </Form.Item>
              <Form.Item label="上传文件">
                <Upload.Dragger
                  multiple
                  accept={allAcceptedExtensions}
                  beforeUpload={() => false}
                  fileList={fileList}
                  onChange={({ fileList: nextList }) => setFileList(nextList)}
                  className="upload-dragger"
                >
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text">拖拽图片、ZIP 或视频到这里，或点击选择文件</p>
                  <p className="ant-upload-hint">单个数据集必须只包含一种数据类型；图片和视频请分开上传。</p>
                </Upload.Dragger>
              </Form.Item>
              {typeMessage}
            </Card>
          </Col>

          <Col xs={24} xl={10}>
            <Card title="创建任务" className="panel-card">
              <Form.Item label="任务类型" name="taskType">
                {isVideo ? (
                  <Radio.Group optionType="button" buttonStyle="solid" value="video_bline_segmentation">
                    <Radio.Button value="video_bline_segmentation">肺超声 B-line 视频关键帧分割</Radio.Button>
                  </Radio.Group>
                ) : (
                  <Radio.Group optionType="button" buttonStyle="solid">
                    <Radio.Button value="bbox">BBox</Radio.Button>
                    <Radio.Button value="polygon">Polygon</Radio.Button>
                    <Radio.Button value="bbox_polygon">BBox + Polygon</Radio.Button>
                  </Radio.Group>
                )}
              </Form.Item>

              {isImage ? (
                <>
                  <Form.Item
                    label="任务名称"
                    name="taskName"
                    rules={[
                      { required: true, message: "请输入任务名称" },
                      { whitespace: true, message: "任务名称不能为空白" },
                      { min: 3, message: "任务名称至少需要 3 个字符" },
                    ]}
                  >
                    <Input placeholder="例如：肺部病灶 bbox + polygon 标注" size="large" />
                  </Form.Item>
                  <Form.Item
                    label="标签名称"
                    name="labelName"
                    rules={[
                      { required: true, message: "请输入标签名称" },
                      { whitespace: true, message: "标签名称不能为空白" },
                    ]}
                  >
                    <Input placeholder="默认使用病灶" />
                  </Form.Item>
                  {selectedTaskType !== "polygon" ? (
                    <Form.Item label="检测模型 ID" name="detModelId">
                      <Input placeholder="例如：mock_detection" />
                    </Form.Item>
                  ) : null}
                  {selectedTaskType !== "bbox" ? (
                    <Form.Item label="分割模型 ID" name="segModelId">
                      <Input placeholder="例如：mock_segmentation" />
                    </Form.Item>
                  ) : null}
                  <Form.Item label="需要人工确认" name="requireHumanConfirm" valuePropName="checked">
                    <Switch checkedChildren="需要" unCheckedChildren="跳过" />
                  </Form.Item>
                </>
              ) : (
                <Alert
                  type={cvatHealth?.reachable && cvatHealth.authenticated ? "success" : "warning"}
                  showIcon
                  message={
                    cvatHealth?.reachable && cvatHealth.authenticated
                      ? "CVAT 视频标注可用，本次视频任务将使用 CVAT。"
                      : "CVAT 当前不可用，本次视频任务将使用兼容的 Label Studio 后端。"
                  }
                  description={cvatHealth?.error || "视频任务的患者与肺区信息请在下方逐视频填写。"}
                />
              )}

              <Button type="primary" size="large" block loading={submitting} onClick={handleSubmit}>
                上传并创建任务
              </Button>
            </Card>
          </Col>
        </Row>
      </Form>

      {isVideo ? (
        <Card title="逐视频元数据" className="panel-card">
          <Alert
            type="warning"
            showIcon
            message="请勿填写患者姓名、身份证等真实隐私信息。patient_uid 应为脱敏编号。"
            style={{ marginBottom: 16 }}
          />
          <Form form={batchForm} layout="vertical">
            <Row gutter={12}>
              <Col xs={24} md={6}>
                <Form.Item label="patient_uid" name="patient_uid">
                  <Input placeholder="Patient_A" />
                </Form.Item>
              </Col>
              <Col xs={24} md={5}>
                <Form.Item label="lung_zone" name="lung_zone">
                  <Input placeholder="R1 / L2" />
                </Form.Item>
              </Col>
              <Col xs={24} md={5}>
                <Form.Item label="probe" name="probe">
                  <Input placeholder="linear" />
                </Form.Item>
              </Col>
              <Col xs={24} md={5}>
                <Form.Item label="device" name="device">
                  <Input placeholder="device group" />
                </Form.Item>
              </Col>
              <Col xs={24} md={3}>
                <Form.Item label="操作">
                  <Space>
                    <Button onClick={() => applyBatch("selected")}>应用到选中</Button>
                    <Button onClick={() => applyBatch("all")}>应用到全部</Button>
                  </Space>
                </Form.Item>
              </Col>
            </Row>
          </Form>
          <Table
            rowKey="key"
            columns={metadataColumns}
            dataSource={videoRows}
            pagination={false}
            scroll={{ x: 1280 }}
            rowSelection={{
              selectedRowKeys: selectedVideoRowKeys,
              onChange: setSelectedVideoRowKeys,
            }}
          />
        </Card>
      ) : null}

      {imageUploadResult ? (
        <Alert
          type="success"
          showIcon
          message="图片数据集上传成功"
          description={`dataset_id: ${imageUploadResult.dataset_id}，图片数：${imageUploadResult.image_count}`}
        />
      ) : null}

      {videoUploadResult ? (
        <Alert
          type="success"
          showIcon
          message="视频数据集上传成功"
          description={`dataset_id: ${videoUploadResult.dataset_id}，视频数：${videoUploadResult.video_count}`}
        />
      ) : null}

      {imageUploadResult?.warnings.length ? (
        <Alert
          type="warning"
          showIcon
          message="部分图片文件被跳过"
          description={imageUploadResult.warnings.map((item) => `${item.filename}: ${item.message}`).join("；")}
        />
      ) : null}

      {videoUploadResult?.warnings.length ? (
        <Alert
          type="warning"
          showIcon
          message="部分视频文件被跳过"
          description={videoUploadResult.warnings.map((item) => `${item.filename}: ${item.message}`).join("；")}
        />
      ) : null}
    </Space>
  );
}
