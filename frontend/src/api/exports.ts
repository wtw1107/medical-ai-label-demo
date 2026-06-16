import type { ExportRequest, ExportResponse, ExportStatusResponse } from "../types/api";
import { apiClient, buildAbsoluteUrl } from "./client";

export async function createExport(taskId: string, payload: ExportRequest) {
  const response = await apiClient.post<ExportResponse>(`/api/tasks/${taskId}/exports`, payload);
  return response.data;
}

export async function getExportStatus(exportId: string) {
  const response = await apiClient.get<ExportStatusResponse>(`/api/exports/${exportId}`);
  return response.data;
}

export function getExportDownloadUrl(exportId: string) {
  return buildAbsoluteUrl(`/api/exports/${exportId}/download`);
}
