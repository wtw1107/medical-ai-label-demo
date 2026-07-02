export type TaskType = "bbox" | "polygon" | "bbox_polygon";
export type ExportFormat = "label_studio_json" | "simple_json" | "mask_png";
export type ExportRange = "confirmed_only";
export type ModelType = "detection" | "segmentation";
export type ModelStatus = "available" | "not_configured";

export interface UploadImageItem {
  id: string;
  dataset_id: string;
  filename: string;
  file_path: string;
  file_url: string;
  width: number | null;
  height: number | null;
  status: string;
  error_message: string | null;
}

export interface UploadWarning {
  filename: string;
  message: string;
}

export interface DatasetUploadResponse {
  dataset_id: string;
  image_count: number;
  images: UploadImageItem[];
  warnings: UploadWarning[];
}

export interface AnnotationTaskCreatePayload {
  dataset_id: string;
  name: string;
  task_type: TaskType;
  label_name: string;
  det_model_id?: string | null;
  seg_model_id?: string | null;
  require_human_confirm: boolean;
}

export interface AnnotationTaskCreateResponse {
  task_id: string;
  dataset_id: string;
  label_studio_project_id: number;
  label_studio_project_url: string;
  status: string;
}

export interface AnnotationTaskDetail {
  task_id: string;
  dataset_id: string;
  name: string;
  task_type: TaskType;
  label_name: string;
  det_model_id?: string | null;
  seg_model_id?: string | null;
  require_human_confirm: boolean;
  label_studio_project_id: number | null;
  label_studio_project_url: string | null;
  status: string;
  error_message: string | null;
}

export interface AnnotationTaskListItem {
  task_id: string;
  task_name: string;
  task_type: TaskType;
  dataset_id: string;
  dataset_name: string | null;
  image_count: number;
  prediction_written_count: number;
  annotation_saved_count: number;
  label_studio_project_id: number | null;
  label_studio_project_url: string | null;
  created_at: string;
  updated_at: string;
  status: string;
}

export interface AnnotationTaskListResponse {
  items: AnnotationTaskListItem[];
  total: number;
}

export interface LabelStudioUrlResponse {
  url: string;
}

export interface ModelInfo {
  model_id: string;
  model_name: string;
  model_type: ModelType;
  model_version: string;
  status: ModelStatus;
  description: string;
}

export interface ModelListResponse {
  items: ModelInfo[];
}

export interface PrelabelRunRequest {
  detection_model_id?: string | null;
  segmentation_model_id?: string | null;
}

export interface PrelabelRunResponse {
  job_id: string;
  task_id: string;
  status: string;
  total_count: number;
  success_count: number;
  failed_count: number;
}

export interface PrelabelJobStatusResponse {
  job_id: string;
  task_id: string;
  status: string;
  total_count: number;
  success_count: number;
  failed_count: number;
  error_message: string | null;
}

export interface TaskImageStatusItem {
  image_id: string;
  filename: string;
  status: string;
  has_prediction: boolean;
  has_annotation: boolean;
  prediction_status?: "none" | "written" | "failed";
  annotation_status?: "unsaved" | "saved";
  label_studio_task_id?: number | null;
  label_studio_task_url?: string | null;
}

export interface TaskImagesResponse {
  task_id: string;
  images: TaskImageStatusItem[];
}

export interface LabelStudioStatusSyncResponse {
  task_id: string;
  synced_count: number;
  prediction_written_count: number;
  annotation_saved_count: number;
  images: TaskImageStatusItem[];
}

export interface PredictionPreviewValue {
  x?: number | null;
  y?: number | null;
  width?: number | null;
  height?: number | null;
  points?: number[][];
}

export interface PredictionPreviewItem {
  type: "rectanglelabels" | "polygonlabels";
  label: string;
  score?: number | null;
  model_id?: string | null;
  model_version?: string | null;
  model_type?: string | null;
  created_at?: string | null;
  value: PredictionPreviewValue;
}

export interface PredictionPreviewResponse {
  task_id: string;
  image_id: string;
  filename: string;
  image_url: string;
  image_width: number | null;
  image_height: number | null;
  label_studio_task_id: number | null;
  label_studio_task_url: string | null;
  has_prediction: boolean;
  model_id: string | null;
  model_version: string | null;
  model_type: string | null;
  predictions: PredictionPreviewItem[];
  raw_prediction_count: number;
}

export interface ExportRequest {
  format: ExportFormat;
  range: ExportRange;
}

export interface ExportResponse {
  export_id: string;
  task_id: string;
  format: ExportFormat;
  status: string;
  file_path: string;
  download_url: string;
}

export interface ExportStatusResponse {
  export_id: string;
  task_id: string;
  format: ExportFormat;
  range: ExportRange;
  status: string;
  file_path: string | null;
  download_url: string | null;
  total_count: number;
  error_message: string | null;
}
