import React, { useEffect, useMemo, useRef, useState } from "react";
import { InboxOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Popover,
  Radio,
  Row,
  Select,
  Space,
  Steps,
  Switch,
  Table,
  Tooltip,
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

type DetectedDataType = "none" | "image" | "video" | "mixed" | "unknown";
type ImageTaskType = "bbox" | "polygon" | "bbox_polygon";
type VideoMetadataRow = VideoUploadMetadata & { key: string };

interface UploadFormValues {
  datasetName: string;
  datasetDescription?: string;
  taskName?: string;
  taskType?: TaskType;
  labelName?: string;
  detModelId?: string;
  segModelId?: string;
  requireHumanConfirm: boolean;
}

const imageExtensions = new Set(["jpg", "jpeg", "png", "bmp", "tif", "tiff", "zip"]);
const videoExtensions = new Set(["mp4", "avi", "mov", "mkv"]);
const allAcceptedExtensions = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".zip", ".mp4", ".avi", ".mov", ".mkv"].join(",");

const deidOptions = [
  { label: "已确认脱敏", value: "confirmed" },
  { label: "待确认", value: "pending" },
  { label: "不适用", value: "not_applicable" },
];

function requiredLabel(text: string) {
  return (
    <span>
      <span style={{ color: "#ff4d4f", marginRight: 4 }}>*</span>
      {text}
    </span>
  );
}

function getExtension(filename: string) {
  const parts = filename.toLowerCase().split(".");
  return parts.length > 1 ? parts[parts.length - 1] || "" : "";
}

function detectDataType(files: UploadFile[]): DetectedDataType {
  if (files.length === 0) {
    return "none";
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
  return fileList.map((item) => item.originFileObj).filter((item): item is RcFile => item instanceof File);
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
    deid_status: existing?.deid_status || "",
  };
}

export function UploadPage() {
  const [form] = Form.useForm<UploadFormValues>();
  const [batchForm] = Form.useForm<Partial<VideoUploadMetadata>>();
  const metadataRef = useRef<HTMLDivElement | null>(null);
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
  const datasetName = Form.useWatch("datasetName", form) || "";

  useEffect(() => {
    if (detectedType === "none") {
      form.setFieldsValue({ taskType: undefined, taskName: undefined });
      setVideoRows([]);
      setSelectedVideoRowKeys([]);
      return;
    }
    if (detectedType === "video") {
      form.setFieldsValue({
        taskType: "video_bline_segmentation",
        labelName: "B-line",
        taskName: form.getFieldValue("taskName") || (datasetName ? `${datasetName}-B-line视频标注` : undefined),
      });
      setVideoRows((currentRows) => fileList.map((file) => makeMetadataRow(file, currentRows.find((row) => row.key === file.uid))));
      return;
    }
    setVideoRows([]);
    setSelectedVideoRowKeys([]);
    if (detectedType === "image") {
      form.setFieldsValue({
        taskType: form.getFieldValue("taskType") === "video_bline_segmentation" || !form.getFieldValue("taskType") ? "bbox_polygon" : form.getFieldValue("taskType"),
        labelName: form.getFieldValue("labelName") && form.getFieldValue("labelName") !== "B-line" ? form.getFieldValue("labelName") : "病灶",
        taskName: form.getFieldValue("taskName") || (datasetName ? `${datasetName}-图片标注` : undefined),
      });
    }
  }, [datasetName, detectedType, fileList, form]);

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
    const patch = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== "")) as Partial<VideoMetadataRow>;
    if (Object.keys(patch).length === 0) {
      message.warning("请先填写要批量应用的视频元数据。");
      return;
    }
    const selected = new Set(selectedVideoRowKeys.map(String));
    if (mode === "selected" && selected.size === 0) {
      message.warning("请先选择要批量填写的视频。");
      return;
    }
    setVideoRows((rows) => rows.map((row) => (mode === "all" || selected.has(row.key) ? { ...row, ...patch } : row)));
    message.success(mode === "all" ? "已应用到全部视频。" : "已应用到选中视频。");
  };

  const validateVideoMetadata = () => {
    const errors = videoRows
      .map((row) => {
        const missing: string[] = [];
        if (!row.patient_uid.trim()) missing.push("患者脱敏编号");
        if (!row.lung_zone.trim()) missing.push("肺区");
        if (!row.deid_status?.trim()) missing.push("脱敏状态");
        return missing.length ? `${row.filename} 缺少${missing.join("、")}` : null;
      })
      .filter((item): item is string => Boolean(item));
    if (errors.length === 0) {
      return true;
    }
    const visible = errors.slice(0, 3).join("；");
    const suffix = errors.length > 3 ? `；另有 ${errors.length - 3} 个文件缺少必填字段。` : "。";
    message.error(`${visible}${suffix}`);
    metadataRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    return false;
  };

  const handleSubmit = async () => {
    try {
      if (detectedType === "none") {
        message.warning("请先选择图片或视频文件。");
        return;
      }
      if (detectedType === "mixed") {
        message.error("同一数据集只能包含一种数据类型，请分开上传图片和视频。");
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
          setSubmitting(false);
          return;
        }
        const result = await uploadVideoDataset({
          dataset_name: values.datasetName.trim(),
          annotation_backend: "cvat",
          metadata: videoRows.map(({ key: _key, ...row }) => ({
            ...row,
            patient_uid: row.patient_uid.trim(),
            lung_zone: row.lung_zone.trim(),
            probe: row.probe?.trim() || null,
            device: row.device?.trim() || null,
            depth: row.depth?.trim() || null,
            orientation: row.orientation?.trim() || null,
            deid_status: row.deid_status?.trim() || "",
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
        name: values.taskName?.trim() || `${values.datasetName.trim()}-图片标注`,
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
      return <Alert type="error" showIcon message="同一数据集只能包含一种数据类型，请分开上传图片和视频。" />;
    }
    if (detectedType === "video") {
      return (
        <Alert
          type="info"
          showIcon
          message="已识别为视频数据集"
          description="仅上传已完成脱敏或使用测试数据的视频。患者脱敏编号不得包含姓名、身份证号等直接身份信息。"
        />
      );
    }
    if (detectedType === "image") {
      return <Alert type="info" showIcon message="已识别为图片数据集" description="可创建目标框、多边形或目标框 + 多边形图片标注任务。" />;
    }
    return <Alert type="info" showIcon message="请选择同一种数据类型的文件" description="支持 jpg/jpeg/png/bmp/tif/tiff/zip 图片数据，以及 mp4/avi/mov/mkv 视频数据。" />;
  }, [detectedType]);

  const metadataColumns = useMemo<ColumnsType<VideoMetadataRow>>(
    () => [
      {
        title: "文件名",
        dataIndex: "filename",
        width: 220,
        fixed: "left",
        render: (value: string) => (
          <Tooltip title={value}>
            <Typography.Text ellipsis style={{ maxWidth: 200 }}>
              {value}
            </Typography.Text>
          </Tooltip>
        ),
      },
      {
        title: requiredLabel("患者脱敏编号"),
        dataIndex: "patient_uid",
        width: 180,
        render: (_, row) => (
          <Input value={row.patient_uid} placeholder="例如：P001" onChange={(event) => updateVideoRow(row.key, { patient_uid: event.target.value })} />
        ),
      },
      {
        title: requiredLabel("肺区"),
        dataIndex: "lung_zone",
        width: 160,
        render: (_, row) => <Input value={row.lung_zone} placeholder="例如：右前上区、R1" onChange={(event) => updateVideoRow(row.key, { lung_zone: event.target.value })} />,
      },
      {
        title: requiredLabel("脱敏状态"),
        dataIndex: "deid_status",
        width: 150,
        render: (_, row) => (
          <Select
            value={row.deid_status || undefined}
            placeholder="请选择脱敏状态"
            style={{ width: "100%" }}
            onChange={(value) => updateVideoRow(row.key, { deid_status: value })}
            options={deidOptions}
          />
        ),
      },
      {
        title: "探头类型",
        dataIndex: "probe",
        width: 130,
        render: (_, row) => <Input value={row.probe || ""} placeholder="例如：线阵、凸阵" onChange={(event) => updateVideoRow(row.key, { probe: event.target.value })} />,
      },
      {
        title: "设备信息",
        dataIndex: "device",
        width: 150,
        render: (_, row) => <Input value={row.device || ""} placeholder="例如：设备型号" onChange={(event) => updateVideoRow(row.key, { device: event.target.value })} />,
      },
      {
        title: "更多信息",
        key: "more",
        width: 120,
        render: (_, row) => (
          <Popover
            trigger="click"
            title="编辑更多信息"
            content={
              <Space direction="vertical" style={{ width: 260 }}>
                <Input value={row.depth || ""} placeholder="成像深度，例如：8 cm" onChange={(event) => updateVideoRow(row.key, { depth: event.target.value })} />
                <Input value={row.orientation || ""} placeholder="扫查方向，例如：纵向、横向" onChange={(event) => updateVideoRow(row.key, { orientation: event.target.value })} />
              </Space>
            }
          >
            <Button>编辑更多信息</Button>
          </Popover>
        ),
      },
    ],
    [],
  );

  const renderTaskConfig = () => {
    if (detectedType === "none" || detectedType === "mixed" || detectedType === "unknown") {
      return (
        <Card title="任务配置" className="panel-card">
          <Empty description="请先选择图片或视频文件。系统识别数据类型后，将显示对应的任务配置。" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        </Card>
      );
    }

    if (detectedType === "video") {
      return (
        <Card title="创建视频标注任务" className="panel-card">
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Alert
              type={cvatHealth?.reachable && cvatHealth.authenticated ? "success" : "warning"}
              showIcon
              message={cvatHealth?.reachable && cvatHealth.authenticated ? "标注工具：CVAT" : "CVAT 当前不可用"}
              description={cvatHealth?.error || "视频任务将在 CVAT 中完成完整视频浏览、关键帧标记、B-line 区域标注和问题复核。"}
            />
            <Typography.Text>数据类型：视频</Typography.Text>
            <Typography.Text>任务类型：B-line 视频分割</Typography.Text>
            <Typography.Text>标签名称：B-line</Typography.Text>
            <Typography.Text type="secondary">输出：关键帧图像与 0/1 mask</Typography.Text>
            <Form.Item
              label="任务名称"
              name="taskName"
              rules={[
                { required: true, message: "请输入任务名称" },
                { whitespace: true, message: "任务名称不能为空" },
              ]}
            >
              <Input placeholder="例如：肺超声 B-line 视频标注" size="large" />
            </Form.Item>
            <Button type="primary" size="large" block loading={submitting} onClick={handleSubmit}>
              上传并创建视频任务
            </Button>
          </Space>
        </Card>
      );
    }

    return (
      <Card title="创建图片标注任务" className="panel-card">
        <Form.Item label="任务类型" name="taskType" rules={[{ required: true, message: "请选择任务类型" }]}>
          <Radio.Group optionType="button" buttonStyle="solid">
            <Radio.Button value="bbox">目标框标注</Radio.Button>
            <Radio.Button value="polygon">多边形分割</Radio.Button>
            <Radio.Button value="bbox_polygon">目标框 + 多边形</Radio.Button>
          </Radio.Group>
        </Form.Item>
        <Form.Item
          label="任务名称"
          name="taskName"
          rules={[
            { required: true, message: "请输入任务名称" },
            { whitespace: true, message: "任务名称不能为空" },
            { min: 3, message: "任务名称至少需要 3 个字符" },
          ]}
        >
          <Input placeholder="例如：肺部病灶图片标注" size="large" />
        </Form.Item>
        <Form.Item
          label="标签名称"
          name="labelName"
          rules={[
            { required: true, message: "请输入标签名称" },
            { whitespace: true, message: "标签名称不能为空" },
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
        <Button type="primary" size="large" block loading={submitting} onClick={handleSubmit}>
          上传并创建图片任务
        </Button>
      </Card>
    );
  };

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={15}>
            <Typography.Title className="hero-title">统一上传与任务创建</Typography.Title>
            <Typography.Paragraph className="hero-description">
              从同一个入口上传医学图片或肺超声 cine-loop 视频。平台会按文件类型显示对应任务配置，并进入图片或视频标注流程。
            </Typography.Paragraph>
          </Col>
          <Col xs={24} xl={9}>
            <Steps
              current={detectedType === "none" ? 0 : 1}
              direction="vertical"
              items={[{ title: "上传图片或视频" }, { title: "按数据类型配置任务" }, { title: "进入任务详情继续标注" }]}
            />
          </Col>
        </Row>
      </Card>

      <Form
        form={form}
        layout="vertical"
        initialValues={{
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
                  { whitespace: true, message: "数据集名称不能为空" },
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
                  onChange={({ fileList: nextList }) => {
                    setFileList(nextList);
                    setImageUploadResult(null);
                    setVideoUploadResult(null);
                  }}
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
          <Col xs={24} xl={10}>{renderTaskConfig()}</Col>
        </Row>
      </Form>

      {detectedType === "video" ? (
        <Card title="逐视频元数据" className="panel-card" ref={metadataRef}>
          <Alert
            type="warning"
            showIcon
            message="仅上传已完成脱敏或使用测试数据的视频。"
            description="患者脱敏编号不得包含姓名、身份证号、住院号等直接身份信息。"
            style={{ marginBottom: 16 }}
          />
          <Form form={batchForm} layout="vertical">
            <Row gutter={[12, 12]} align="bottom">
              <Col xs={24} md={5}>
                <Form.Item label={requiredLabel("患者脱敏编号")} name="patient_uid" extra="使用脱敏后的研究编号，不填写真实姓名或身份证号。">
                  <Input placeholder="例如：P001" />
                </Form.Item>
              </Col>
              <Col xs={24} md={4}>
                <Form.Item label={requiredLabel("肺区")} name="lung_zone">
                  <Input placeholder="例如：右前上区、R1" />
                </Form.Item>
              </Col>
              <Col xs={24} md={4}>
                <Form.Item label={requiredLabel("脱敏状态")} name="deid_status">
                  <Select placeholder="请选择脱敏状态" options={deidOptions} />
                </Form.Item>
              </Col>
              <Col xs={24} md={4}>
                <Form.Item label="探头类型" name="probe">
                  <Input placeholder="例如：线阵、凸阵" />
                </Form.Item>
              </Col>
              <Col xs={24} md={4}>
                <Form.Item label="设备信息" name="device">
                  <Input placeholder="例如：设备型号或设备组" />
                </Form.Item>
              </Col>
              <Col xs={24} md={3}>
                <Space wrap>
                  <Button disabled={selectedVideoRowKeys.length === 0} onClick={() => applyBatch("selected")}>
                    应用到选中视频
                  </Button>
                  <Button onClick={() => applyBatch("all")}>应用到全部视频</Button>
                </Space>
              </Col>
            </Row>
          </Form>
          <Table
            rowKey="key"
            columns={metadataColumns}
            dataSource={videoRows}
            pagination={false}
            scroll={{ x: 1080 }}
            rowSelection={{
              selectedRowKeys: selectedVideoRowKeys,
              onChange: setSelectedVideoRowKeys,
            }}
          />
        </Card>
      ) : null}

      {imageUploadResult ? (
        <Alert type="success" showIcon message="图片数据集上传成功" description={`dataset_id: ${imageUploadResult.dataset_id}，图片数：${imageUploadResult.image_count}`} />
      ) : null}
      {videoUploadResult ? (
        <Alert type="success" showIcon message="视频数据集上传成功" description={`dataset_id: ${videoUploadResult.dataset_id}，视频数：${videoUploadResult.video_count}`} />
      ) : null}
    </Space>
  );
}
