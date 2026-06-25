export type TaskType = "bbox" | "polygon" | "bbox_polygon";
export type ExportFormat = "label_studio_json" | "simple_json" | "mask_png";
export type ExportRange = "confirmed_only";

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

export interface LabelStudioUrlResponse {
  url: string;
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
  label_studio_task_id?: number | null;
  label_studio_task_url?: string | null;
}

export interface TaskImagesResponse {
  task_id: string;
  images: TaskImageStatusItem[];
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
