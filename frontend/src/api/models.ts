import type { ModelListResponse } from "../types/api";
import { apiClient } from "./client";

export async function listModels() {
  const response = await apiClient.get<ModelListResponse>("/api/models");
  return response.data;
}
