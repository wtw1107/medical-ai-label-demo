import React, { useEffect, useMemo, useState } from "react";
import { InboxOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Form, Input, Radio, Row, Select, Space, Steps, Switch, Typography, Upload, message } from "antd";
import type { RcFile, UploadFile } from "antd/es/upload/interface";
import { useNavigate } from "react-router-dom";

import { uploadDataset } from "../api/datasets";
import { createTask } from "../api/tasks";
import { uploadVideoDataset } from "../api/videos";
import type { DatasetUploadResponse, TaskType, VideoDatasetUploadResponse } from "../types/api";

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
  patientUid?: string;
  lungZone?: string;
  probe?: string;
  device?: string;
  depth?: string;
  orientation?: string;
  deidStatus?: string;
}

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

export function UploadPage() {
  const [form] = Form.useForm<UploadFormValues>();
  const navigate = useNavigate();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [imageUploadResult, setImageUploadResult] = useState<DatasetUploadResponse | null>(null);
  const [videoUploadResult, setVideoUploadResult] = useState<VideoDatasetUploadResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const detectedType = useMemo(() => detectDataType(fileList), [fileList]);
  const selectedTaskType = Form.useWatch("taskType", form) || "bbox_polygon";
  const isVideo = detectedType === "video";
  const isImage = detectedType === "image" || detectedType === "unknown";

  useEffect(() => {
    if (detectedType === "video") {
      form.setFieldsValue({ taskType: "video_bline_segmentation" });
      return;
    }
    if (detectedType === "image" && form.getFieldValue("taskType") === "video_bline_segmentation") {
      form.setFieldsValue({ taskType: "bbox_polygon" });
    }
  }, [detectedType, form]);

  const steps = useMemo(
    () => [
      { title: "上传图片或视频" },
      { title: "按数据类型选择任务" },
      { title: "进入任务详情继续标注" },
    ],
    [],
  );

  const handleSubmit = async () => {
    try {
      if (fileList.length === 0) {
        message.warning("请先选择至少一个图片、ZIP 或视频文件。");
        return;
      }
      if (detectedType === "mixed") {
        message.error("当前一个数据集只能包含一种数据类型，请分别上传图片和视频。");
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
        const result = await uploadVideoDataset({
          dataset_name: values.datasetName.trim(),
          patient_uid: values.patientUid?.trim() || "",
          lung_zone: values.lungZone?.trim(),
          probe: values.probe?.trim(),
          device: values.device?.trim(),
          depth: values.depth?.trim(),
          orientation: values.orientation?.trim(),
          deid_status: values.deidStatus,
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
      return (
        <Alert
          type="error"
          showIcon
          message="当前一个数据集只能包含一种数据类型，请分别上传图片和视频。"
        />
      );
    }
    if (detectedType === "video") {
      return (
        <Alert
          type="info"
          showIcon
          message="已识别为视频数据集"
          description="本阶段仅支持肺超声 B-line 视频关键帧分割任务。"
        />
      );
    }
    if (detectedType === "image") {
      return (
        <Alert
          type="info"
          showIcon
          message="已识别为图片数据集"
          description="可创建 bbox、polygon 或 bbox + polygon 图片标注任务。"
        />
      );
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

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={15}>
            <Typography.Title className="hero-title">统一上传与任务创建</Typography.Title>
            <Typography.Paragraph className="hero-description">
              从同一个入口上传医学图片或肺超声 cine-loop 视频。平台会根据文件类型显示可用任务类型，并把图片任务与视频任务带到对应的任务详情流程。
            </Typography.Paragraph>
          </Col>
          <Col xs={24} xl={9}>
            <Steps current={1} direction="vertical" items={steps} />
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
          deidStatus: "unknown",
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
                  <p className="ant-upload-hint">
                    单个数据集必须只包含一种数据类型；图片和视频请分开上传。后端仍会执行最终文件解析和安全校验。
                  </p>
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
              ) : null}

              {isVideo ? (
                <>
                  <Form.Item
                    label="患者 UID"
                    name="patientUid"
                    rules={[
                      { required: true, message: "请输入脱敏后的患者 UID" },
                      { whitespace: true, message: "患者 UID 不能为空白" },
                    ]}
                  >
                    <Input placeholder="请勿填写患者真实姓名或身份证等隐私信息" />
                  </Form.Item>
                  <Row gutter={12}>
                    <Col span={12}>
                      <Form.Item label="肺区" name="lungZone">
                        <Input placeholder="例如：R1 / L2" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="探头" name="probe">
                        <Input placeholder="例如：linear" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={12}>
                    <Col span={12}>
                      <Form.Item label="设备" name="device">
                        <Input placeholder="设备型号或分组" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="深度" name="depth">
                        <Input placeholder="例如：4cm" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Form.Item label="方向" name="orientation">
                    <Input placeholder="例如：longitudinal / transverse" />
                  </Form.Item>
                  <Form.Item label="脱敏状态" name="deidStatus">
                    <Select
                      options={[
                        { label: "unknown", value: "unknown" },
                        { label: "passed", value: "passed" },
                        { label: "failed", value: "failed" },
                        { label: "needs_review", value: "needs_review" },
                      ]}
                    />
                  </Form.Item>
                </>
              ) : null}

              <Button type="primary" size="large" block loading={submitting} onClick={handleSubmit}>
                上传并创建任务
              </Button>
            </Card>
          </Col>
        </Row>
      </Form>

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
