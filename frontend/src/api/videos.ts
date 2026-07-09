import type {
  KeyFrameExtractRequest,
  KeyFrameExtractResponse,
  KeyFrameListResponse,
  VideoDatasetSummary,
  VideoDatasetUploadResponse,
  VideoListResponse,
  VideoReview,
  VideoReviewUpdateRequest,
} from "../types/api";
import { apiClient } from "./client";

export interface UploadVideoDatasetPayload {
  dataset_name: string;
  patient_uid: string;
  lung_zone?: string;
  probe?: string;
  device?: string;
  depth?: string;
  orientation?: string;
  deid_status?: string;
  files: File[];
}

export async function uploadVideoDataset(payload: UploadVideoDatasetPayload) {
  const formData = new FormData();
  formData.append("dataset_name", payload.dataset_name);
  formData.append("patient_uid", payload.patient_uid);
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
