import { InboxOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Form, Input, Radio, Row, Space, Steps, Switch, Typography, Upload, message } from "antd";
import type { RcFile, UploadFile } from "antd/es/upload/interface";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { uploadDataset } from "../api/datasets";
import { createTask } from "../api/tasks";
import type { DatasetUploadResponse, TaskType } from "../types/api";

interface UploadFormValues {
  datasetName: string;
  datasetDescription?: string;
  taskName: string;
  taskType: TaskType;
  labelName: string;
  detModelId?: string;
  segModelId?: string;
  requireHumanConfirm: boolean;
}

export function UploadPage() {
  const [form] = Form.useForm<UploadFormValues>();
  const navigate = useNavigate();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploadResult, setUploadResult] = useState<DatasetUploadResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const selectedTaskType = Form.useWatch("taskType", form) || "bbox_polygon";

  const steps = useMemo(
    () => [
      { title: "上传图像或 ZIP" },
      { title: "创建 AI 辅助标注任务" },
      { title: "进入任务详情与 Label Studio" },
    ],
    [],
  );

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (fileList.length === 0) {
        message.warning("请先选择至少一个图片或 ZIP 文件。");
        return;
      }

      setSubmitting(true);
      const datasetName = values.datasetName.trim();
      const datasetDescription = values.datasetDescription?.trim();
      const taskName = values.taskName.trim();
      const labelName = values.labelName.trim();
      const files = fileList
        .map((item) => item.originFileObj)
        .filter((item): item is RcFile => item instanceof File);

      const dataset = await uploadDataset({
        name: datasetName,
        description: datasetDescription,
        files,
      });
      setUploadResult(dataset);

      const task = await createTask({
        dataset_id: dataset.dataset_id,
        name: taskName,
        task_type: values.taskType,
        label_name: labelName,
        det_model_id: values.detModelId || null,
        seg_model_id: values.segModelId || null,
        require_human_confirm: values.requireHumanConfirm,
      });

      message.success("任务已创建，下面可以进入详情页继续触发 AI 预标注。");
      navigate(`/tasks/${task.task_id}`);
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="hero-card">
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} xl={15}>
            <Typography.Title className="hero-title">
              轻量前端工作台，串起 AI 辅助标注全流程
            </Typography.Title>
            <Typography.Paragraph className="hero-description">
              上传医学影像、创建任务、触发 AI 预标注、跳转 Label Studio 完成人工审核，再将确认结果导出为训练可用文件。
            </Typography.Paragraph>
          </Col>
          <Col xs={24} xl={9}>
            <Steps current={1} direction="vertical" items={steps} />
          </Col>
        </Row>
      </Card>

      <Row gutter={[24, 24]}>
        <Col xs={24} xl={14}>
          <Card title="上传数据集" className="panel-card">
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
              <Form.Item
                label="数据集名称"
                name="datasetName"
                rules={[
                  { required: true, message: "请输入数据集名称" },
                  { whitespace: true, message: "数据集名称不能为空白" },
                ]}
              >
                <Input placeholder="例如：肺部病灶样例集" size="large" />
              </Form.Item>
              <Form.Item label="数据集说明" name="datasetDescription">
                <Input.TextArea rows={3} placeholder="可选，描述数据来源或使用目的" />
              </Form.Item>
              <Form.Item label="上传文件">
                <Upload.Dragger
                  multiple
                  accept=".png,.jpg,.jpeg,.zip"
                  beforeUpload={() => false}
                  fileList={fileList}
                  onChange={({ fileList: nextList }) => setFileList(nextList)}
                  className="upload-dragger"
                >
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text">拖拽图片或 ZIP 到这里，或点击选择文件</p>
                  <p className="ant-upload-hint">
                    支持单张图片、多张图片和 ZIP。前端只负责发起上传，解析与存储由后端完成。
                  </p>
                </Upload.Dragger>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card title="创建 AI 辅助标注任务" className="panel-card">
            <Form form={form} layout="vertical">
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
              <Form.Item label="任务类型" name="taskType">
                <Radio.Group optionType="button" buttonStyle="solid">
                  <Radio.Button value="bbox">BBox</Radio.Button>
                  <Radio.Button value="polygon">Polygon</Radio.Button>
                  <Radio.Button value="bbox_polygon">BBox + Polygon</Radio.Button>
                </Radio.Group>
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
              <Button type="primary" size="large" block loading={submitting} onClick={handleSubmit}>
                上传并创建任务
              </Button>
            </Form>
          </Card>
        </Col>
      </Row>

      {uploadResult ? (
        <Alert
          type="success"
          showIcon
          message="数据集上传成功"
          description={`dataset_id: ${uploadResult.dataset_id}，图片数：${uploadResult.image_count}`}
        />
      ) : null}

      {uploadResult?.warnings.length ? (
        <Alert
          type="warning"
          showIcon
          message="部分文件被跳过"
          description={uploadResult.warnings.map((item) => `${item.filename}: ${item.message}`).join("；")}
        />
      ) : null}
    </Space>
  );
}
