import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { TaskListPage } from "./pages/TaskListPage";
import { TaskDetailPage } from "./pages/TaskDetailPage";
import { UploadPage } from "./pages/UploadPage";
import { VideoDatasetDetailPage } from "./pages/VideoDatasetDetailPage";
import { NativeVideoWorkbenchPage } from "./pages/NativeVideoWorkbenchPage";
import { VideoReviewPage } from "./pages/VideoReviewPage";

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/tasks" element={<TaskListPage />} />
        <Route path="/tasks/video/:datasetId" element={<VideoDatasetDetailPage />} />
        <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
        <Route path="/video-datasets/new" element={<Navigate to="/" replace />} />
        <Route path="/video-datasets/:datasetId" element={<VideoDatasetDetailPage />} />
        <Route path="/video-datasets/:datasetId/videos/:videoId/native-workbench" element={<NativeVideoWorkbenchPage />} />
        <Route path="/video-datasets/:datasetId/videos/:videoId" element={<VideoReviewPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}
