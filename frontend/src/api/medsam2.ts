import { apiClient } from "./client";

export type MedSamPointLabel = 0 | 1;
export type MedSamPromptType = "point" | "box";
export type MedSamBackendMode = "mock" | "real";

export interface MedSamPointPrompt {
  type: "point";
  label: MedSamPointLabel;
  point: [number, number];
}

export interface MedSamBoxPrompt {
  type: "box";
  box: [number, number, number, number];
}

export type MedSamPrompt = MedSamPointPrompt | MedSamBoxPrompt;

export interface MedSamRleMask {
  size: [number, number];
  counts: number[];
  order: "row-major";
}

export interface MedSamPredictFrameRequest {
  task_id: string;
  video_id: string;
  session_id: string;
  video_ref: string;
  frame_index: number;
  object_id: string;
  prompts: MedSamPrompt[];
}

export interface MedSamPredictFrameResponse {
  request_id: string;
  session_id: string;
  video_id: string;
  frame_index: number;
  object_id: string;
  mask: MedSamRleMask;
  score: number;
  backend: MedSamBackendMode;
  status: "completed";
}

export function buildMockPredictFrameResponse(
  request: MedSamPredictFrameRequest,
  width: number,
  height: number,
): MedSamPredictFrameResponse {
  const firstPositive = request.prompts.find((prompt): prompt is MedSamPointPrompt => prompt.type === "point" && prompt.label === 1);
  const centerX = Math.max(0, Math.min(width - 1, Math.round(firstPositive?.point[0] ?? width / 2)));
  const centerY = Math.max(0, Math.min(height - 1, Math.round(firstPositive?.point[1] ?? height / 2)));
  const radiusX = Math.max(16, Math.round(width * 0.08));
  const radiusY = Math.max(16, Math.round(height * 0.11));
  const bits: number[] = [];

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const normalized = ((x - centerX) ** 2) / (radiusX ** 2) + ((y - centerY) ** 2) / (radiusY ** 2);
      bits.push(normalized <= 1 ? 1 : 0);
    }
  }

  return {
    request_id: `mock-${Date.now()}`,
    session_id: request.session_id,
    video_id: request.video_id,
    frame_index: request.frame_index,
    object_id: request.object_id,
    mask: {
      size: [height, width],
      counts: encodeBinaryMaskToRle(bits),
      order: "row-major",
    },
    score: 0.88,
    backend: "mock",
    status: "completed",
  };
}

export async function predictFrameWithRealService(request: MedSamPredictFrameRequest) {
  const response = await apiClient.post<MedSamPredictFrameResponse>("/api/medsam2/predict-frame", request);
  return response.data;
}

export function encodeBinaryMaskToRle(bits: number[]) {
  const counts: number[] = [];
  let expected = 0;
  let runLength = 0;

  for (const bit of bits) {
    if (bit === expected) {
      runLength += 1;
      continue;
    }
    counts.push(runLength);
    expected = bit;
    runLength = 1;
  }
  counts.push(runLength);
  return counts;
}

export function decodeRleMask(mask: MedSamRleMask) {
  const [height, width] = mask.size;
  const bits: number[] = [];
  let value = 0;
  for (const count of mask.counts) {
    for (let index = 0; index < count; index += 1) {
      bits.push(value);
    }
    value = value === 0 ? 1 : 0;
  }
  return { width, height, bits: bits.slice(0, width * height) };
}
