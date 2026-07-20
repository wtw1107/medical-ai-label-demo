import type {
  KeyFrameExtractRequest,
  KeyFrameExtractResponse,
  KeyFrameLabelStudioInitRequest,
  KeyFrameLabelStudioInitResponse,
  KeyFrameLabelStudioSyncResponse,
  KeyFrameListResponse,
  CvatAnnotationSummaryResponse,
  CvatHealthResponse,
  CvatInitResponse,
  CvatSyncResponse,
  VideoDatasetListResponse,
  VideoDatasetSummary,
  VideoDatasetUploadResponse,
  VideoKeyframeExportResponse,
  VideoUploadMetadata,
  VideoListResponse,
  VideoReview,
  VideoReviewUpdateRequest,
  CvatAccessResponse,
} from "../types/api";
import { apiClient } from "./client";

export interface UploadVideoDatasetPayload {
  dataset_name: string;
  patient_uid?: string;
  lung_zone?: string;
  probe?: string;
  device?: string;
  depth?: string;
  orientation?: string;
  deid_status?: string;
  annotation_backend?: "native" | "cvat" | "label_studio";
  metadata?: VideoUploadMetadata[];
  files: File[];
}

export async function uploadVideoDataset(payload: UploadVideoDatasetPayload) {
  const formData = new FormData();
  formData.append("dataset_name", payload.dataset_name);
  if (payload.patient_uid) {
    formData.append("patient_uid", payload.patient_uid);
  }
  if (payload.metadata) {
    formData.append("metadata_json", JSON.stringify(payload.metadata));
  }
  if (payload.annotation_backend) {
    formData.append("annotation_backend", payload.annotation_backend);
  }
  formData.append("lung_zone", payload.lung_zone || "");
  formData.append("probe", payload.probe || "");
  formData.append("device", payload.device || "");
  formData.append("depth", payload.depth || "");
  formData.append("orientation", payload.orientation || "");
  formData.append("deid_status", payload.deid_status || "");
  payload.files.forEach((file) => formData.append("files", file));

  const response = await apiClient.post<VideoDatasetUploadResponse>("/api/video-datasets/upload", formData, {
    timeout: 300000,
  });
  return response.data;
}

export async function getVideoDataset(datasetId: string) {
  const response = await apiClient.get<VideoDatasetSummary>(`/api/video-datasets/${datasetId}`);
  return response.data;
}

export async function listVideoDatasets() {
  const response = await apiClient.get<VideoDatasetListResponse>("/api/video-datasets");
  return response.data;
}

export async function listDatasetVideos(datasetId: string) {
  const response = await apiClient.get<VideoListResponse>(`/api/video-datasets/${datasetId}/videos`);
  return response.data;
}

export async function updateVideoReview(videoId: string, payload: VideoReviewUpdateRequest) {
  const response = await apiClient.patch<VideoReview>(`/api/videos/${videoId}/review`, payload);
  return response.data;
}

export async function extractVideoKeyframes(videoId: string, payload: KeyFrameExtractRequest) {
  const response = await apiClient.post<KeyFrameExtractResponse>(`/api/videos/${videoId}/keyframes/extract`, payload);
  return response.data;
}

export async function listVideoKeyframes(videoId: string) {
  const response = await apiClient.get<KeyFrameListResponse>(`/api/videos/${videoId}/keyframes`);
  return response.data;
}

export async function initKeyframeLabelStudio(videoId: string, payload: KeyFrameLabelStudioInitRequest = {}) {
  const response = await apiClient.post<KeyFrameLabelStudioInitResponse>(`/api/videos/${videoId}/keyframes/label-studio/init`, payload);
  return response.data;
}

export async function syncKeyframeLabelStudioStatus(videoId: string) {
  const response = await apiClient.post<KeyFrameLabelStudioSyncResponse>(`/api/videos/${videoId}/keyframes/sync-label-studio-status`);
  return response.data;
}

export async function exportBlineKeyframes(datasetId: string) {
  const response = await apiClient.post<VideoKeyframeExportResponse>(`/api/video-datasets/${datasetId}/exports/bline-keyframes`);
  return response.data;
}

export async function getCvatHealth() {
  const response = await apiClient.get<CvatHealthResponse>("/api/integrations/cvat/health");
  return response.data;
}

export async function initDatasetCvat(datasetId: string) {
  const response = await apiClient.post<CvatInitResponse>(`/api/video-datasets/${datasetId}/cvat/init`);
  return response.data;
}

export async function syncDatasetCvat(datasetId: string) {
  const response = await apiClient.post<CvatSyncResponse>(`/api/video-datasets/${datasetId}/cvat/sync`);
  return response.data;
}

export async function getCvatAnnotationSummary(videoId: string) {
  const response = await apiClient.get<CvatAnnotationSummaryResponse>(`/api/videos/${videoId}/cvat/annotations-summary`);
  return response.data;
}

export async function getCvatAccess(videoId: string) {
  const response = await apiClient.get<CvatAccessResponse>(`/api/videos/${videoId}/cvat/access`);
  return response.data;
}

export async function exportCvatBlineTest(datasetId: string) {
  const response = await apiClient.post<VideoKeyframeExportResponse>(`/api/video-datasets/${datasetId}/exports/cvat-bline-test`);
  return response.data;
}
