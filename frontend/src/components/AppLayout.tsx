import React from "react";
import { Layout, Menu, Typography } from "antd";
import type { PropsWithChildren } from "react";
import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

const { Header, Sider, Content } = Layout;

export function AppLayout({ children }: PropsWithChildren) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  const items = useMemo(
    () => [
      {
        key: "/tasks",
        label: <Link to="/tasks">任务列表</Link>,
      },
      {
        key: "/",
        label: <Link to="/">上传与任务创建</Link>,
      },
    ],
    [],
  );

  const selectedKey =
    location.pathname.startsWith("/tasks") || location.pathname.startsWith("/video-datasets") ? "/tasks" : "/";

  return (
    <Layout className="app-shell">
      <Sider
        breakpoint="lg"
        collapsedWidth={0}
        collapsible
        collapsed={collapsed}
        onCollapse={(value) => setCollapsed(value)}
        className="app-sider"
        width={260}
      >
        <div className="brand-block">
          <Typography.Title level={4} className="brand-title">
            Medical AI Label
          </Typography.Title>
          <Typography.Paragraph className="brand-subtitle">
            本地医学影像 AI 辅助标注 Demo
          </Typography.Paragraph>
        </div>
        <Menu theme="dark" mode="inline" items={items} selectedKeys={[selectedKey]} />
      </Sider>
      <Layout>
        <Header className="app-header">
          <div>
            <Typography.Title level={3} className="page-title">
              AI 辅助标注工作台
            </Typography.Title>
            <Typography.Text className="page-subtitle">
              统一管理图片任务与肺超声 B-line 视频关键帧分割任务
            </Typography.Text>
          </div>
        </Header>
        <Content className="app-content">{children}</Content>
      </Layout>
    </Layout>
  );
}
