import { ExpandOutlined, ExportOutlined, ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, Space, Typography, message } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";

interface WorkbenchPanelProps {
  projectUrl: string | null;
  taskUrl?: string | null;
  selectedImageName?: string | null;
  onOpenExternal?: (url: string) => void;
  refreshToken?: number;
}

export function WorkbenchPanel({
  projectUrl,
  taskUrl,
  selectedImageName,
  onOpenExternal,
  refreshToken = 0,
}: WorkbenchPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [iframeLoaded, setIframeLoaded] = useState(false);
  const [localRefreshToken, setLocalRefreshToken] = useState(0);

  const resolvedUrl = taskUrl || projectUrl || null;
  const iframeKey = useMemo(
    () => `${resolvedUrl || "empty"}-${refreshToken}-${localRefreshToken}`,
    [localRefreshToken, refreshToken, resolvedUrl],
  );

  useEffect(() => {
    setIframeLoaded(false);
  }, [iframeKey]);

  const handleOpenExternal = () => {
    if (!resolvedUrl) {
      message.warning("暂无可用的 Label Studio 工作台链接。");
      return;
    }

    if (onOpenExternal) {
      onOpenExternal(resolvedUrl);
      return;
    }

    window.open(resolvedUrl, "_blank", "noopener,noreferrer");
  };

  const handleFullscreen = async () => {
    if (!containerRef.current?.requestFullscreen) {
      message.info("当前浏览器不支持工作台全屏显示。");
      return;
    }

    try {
      await containerRef.current.requestFullscreen();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "进入全屏失败。");
    }
  };

  return (
    <Card
      title="标注工作台"
      className="panel-card"
      extra={
        <Space wrap>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => setLocalRefreshToken((value) => value + 1)}
            disabled={!resolvedUrl}
          >
            刷新工作台
          </Button>
          <Button icon={<ExpandOutlined />} onClick={() => void handleFullscreen()} disabled={!resolvedUrl}>
            全屏显示
          </Button>
          <Button icon={<ExportOutlined />} onClick={handleOpenExternal} disabled={!resolvedUrl}>
            在新窗口打开 Label Studio
          </Button>
        </Space>
      }
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          message="首次使用请先登录本地 Label Studio。登录后返回本页面刷新工作台。"
        />
        <Alert
          type="success"
          showIcon
          message="AI 预标注结果已经写入 Label Studio prediction。请在工作台中确认或修正后保存 annotation。保存后可回到本页面同步状态并导出。"
        />
        <div className="workbench-meta">
          <Typography.Text strong>
            {selectedImageName ? `当前正在标注：${selectedImageName}` : "当前查看整个任务工作台"}
          </Typography.Text>
          <Typography.Text type="secondary">
            {resolvedUrl ? "如果页面未显示，可先在新窗口登录 Label Studio 再返回刷新。" : "请先完成任务创建并同步 Label Studio 链接。"}
          </Typography.Text>
        </div>

        {!resolvedUrl ? (
          <Empty description="暂无可用的 Label Studio 工作台链接" />
        ) : (
          <div ref={containerRef} className="workbench-frame-shell">
            {!iframeLoaded ? (
              <Alert
                type="warning"
                showIcon
                message="若工作台为空白或被浏览器阻止，请先在新窗口打开 Label Studio 登录，再回到这里刷新。"
              />
            ) : null}
            <iframe
              key={iframeKey}
              title="Label Studio Workbench"
              src={resolvedUrl}
              className="workbench-frame"
              onLoad={() => setIframeLoaded(true)}
            />
          </div>
        )}
      </Space>
    </Card>
  );
}
