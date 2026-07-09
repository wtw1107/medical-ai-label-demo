import React from "react";
import { InboxOutlined } from "@ant-design/icons";
import { Alert, App, Button, Card, Col, Form, Input, Row, Select, Space, Steps, Typography, Upload } from "antd";
import type { RcFile, UploadFile } from "antd/es/upload/interface";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { uploadVideoDataset } from "../api/videos";
import type { VideoDatasetUploadResponse } from "../types/api";

interface VideoUploadFormValues {
  dataset_name: string;
  patient_uid: string;
  lung_zone?: string;
  probe?: string;
  device?: string;
  depth?: string;
  orientation?: string;
  deid_status?: string;
}

const deidOptions = [
  { label: "passed", value: "passed" },
  { label: "needs_review", value: "needs_review" },
  { label: "unknown", value: "unknown" },
  { label: "failed", value: "failed" },
];

export function VideoDatasetUploadPage() {
  const [form] = Form.useForm<VideoUploadFormValues>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [uploadResult, setUploadResult] = useState<VideoDatasetUploadResponse | null>(null);

  const steps = useMemo(
    () => [
      { title: "上传视频文件" },
      { title: "生成视频数据集" },
      { title: "进入视频审核" },
    ],
    [],
  );

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (fileList.length === 0) {
        message.warning("请先选择至少一个视频文件。");
        return;
      }

      const files = fileList
        .map((item) => item.originFileObj)
        .filter((item): item is RcFile => item instanceof File);

      setSubmitting(true);
      const result = await uploadVideoDataset({
        dataset_name: values.dataset_name.trim(),
        patient_uid: values.patient_uid.trim(),
        lung_zone: values.lung_zone?.trim(),
        probe: values.probe?.trim(),
        device: values.device?.trim(),
        depth: values.depth?.trim(),
        orientation: values.orientation?.trim(),
        deid_status: values.deid_status,
        files,
      });
      setUploadResult(result);
      message.success("视频数据集上传成功，正在进入详情页。");
      navigate(`/video-datasets/${result.dataset_id}`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "视频上传失败。");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={15}>
            <Typography.Title className="hero-title">肺超声 B 线视频关键帧标注 MVP</Typography.Title>
            <Typography.Paragraph className="hero-description">
              当前为肺超声 B 线视频关键帧标注 MVP。医生或项目成员可先上传脱敏视频，记录视频级审核信息，再抽取关键帧进入后续 mask 标注流程。
            </Typography.Paragraph>
          </Col>
          <Col xs={24} xl={9}>
            <Steps current={0} direction="vertical" items={steps} />
          </Col>
        </Row>
      </Card>

      <Alert
        type="info"
        showIcon
        message="当前阶段仅包含视频数据集上传、视频审核和关键帧抽取，不包含 CVAT、视频 AI 预标注或正式仲裁流程。"
      />
      <Alert type="warning" showIcon message="视频文件不会提交到 Git。请确认上传内容已经脱敏，且不包含真实患者隐私信息。" />

      <Row gutter={[24, 24]}>
        <Col xs={24} xl={15}>
          <Card title="上传视频数据集" className="panel-card">
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                deid_status: "unknown",
              }}
            >
              <Form.Item
                label="数据集名称"
                name="dataset_name"
                rules={[
                  { required: true, message: "请输入数据集名称" },
                  { whitespace: true, message: "数据集名称不能为空白" },
                ]}
              >
                <Input placeholder="例如：lung-bline-trial-001" size="large" />
              </Form.Item>
              <Form.Item
                label="患者编号"
                name="patient_uid"
                rules={[
                  { required: true, message: "请输入患者编号" },
                  { whitespace: true, message: "患者编号不能为空白" },
                ]}
              >
                <Input placeholder="例如：PATIENT_001" size="large" />
              </Form.Item>
              <Row gutter={[16, 0]}>
                <Col xs={24} md={12}>
                  <Form.Item label="肺区" name="lung_zone">
                    <Input placeholder="例如：L1 / R3" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="探头" name="probe">
                    <Input placeholder="例如：convex / linear" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="设备" name="device">
                    <Input placeholder="例如：Mindray" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="深度" name="depth">
                    <Input placeholder="例如：6cm" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="方向" name="orientation">
                    <Input placeholder="例如：longitudinal" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item label="脱敏状态" name="deid_status">
                    <Select options={deidOptions} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="视频文件">
                <Upload.Dragger
                  multiple
                  accept=".mp4,.avi,.mov,.mkv"
                  beforeUpload={() => false}
                  fileList={fileList}
                  onChange={({ fileList: nextList }) => setFileList(nextList)}
                  className="upload-dragger"
                >
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text">拖拽视频文件到这里，或点击选择文件</p>
                  <p className="ant-upload-hint">支持 mp4 / avi / mov / mkv。后端会解析 fps、时长、帧数和首帧预览。</p>
                </Upload.Dragger>
              </Form.Item>

              <Button type="primary" size="large" block loading={submitting} onClick={handleSubmit}>
                上传视频数据集
              </Button>
            </Form>
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Card title="使用说明" className="panel-card">
            <Space direction="vertical" size={14} style={{ width: "100%" }}>
              <Typography.Paragraph className="muted-paragraph">
                当前前端只负责最小视频审核流程，不做视频 AI 预标注，也不接入 CVAT。
              </Typography.Paragraph>
              <Typography.Paragraph className="muted-paragraph">
                上传成功后将进入视频数据集详情页，查看视频列表、审核状态和关键帧数量。
              </Typography.Paragraph>
              <Typography.Paragraph className="muted-paragraph">
                进入单个视频审核页后，可以先看完整视频，再记录质量、B 线等级与关键帧。
              </Typography.Paragraph>
            </Space>
          </Card>
        </Col>
      </Row>

      {uploadResult ? (
        <Alert
          type="success"
          showIcon
          message="视频数据集上传成功"
          description={`dataset_id: ${uploadResult.dataset_id}，视频数：${uploadResult.video_count}，患者数：${uploadResult.patient_count}`}
        />
      ) : null}
    </Space>
  );
}
