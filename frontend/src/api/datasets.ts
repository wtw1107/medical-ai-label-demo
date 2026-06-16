import type { DatasetUploadResponse } from "../types/api";
import { apiClient } from "./client";

export interface UploadDatasetPayload {
  name: string;
  description?: string;
  createdBy?: string;
  files: File[];
}

export async function uploadDataset(payload: UploadDatasetPayload) {
  const formData = new FormData();
  formData.append("name", payload.name);
  formData.append("description", payload.description || "");
  formData.append("created_by", payload.createdBy || "local_demo_user");
  payload.files.forEach((file) => formData.append("files", file));

  const response = await apiClient.post<DatasetUploadResponse>("/api/datasets/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return response.data;
}
