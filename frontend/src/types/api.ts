export type TaskType = "bbox" | "polygon" | "bbox_polygon" | "video_bline_segmentation";
export type ExportFormat = "label_studio_json" | "simple_json" | "mask_png";
export type ExportRange = "confirmed_only";
export type ModelType = "detection" | "segmentation";
export type ModelStatus = "available" | "not_configured";
export type ModelDeploymentType = "mock" | "external_api" | "local_model_placeholder";
export type VideoQuality = "good" | "usable" | "poor" | "unknown";
export type BLineGrade = "0" | "1-2" | "3+" | "confluent" | "unknown";
export type KeyFrameReason =
  | "first_clear"
  | "most_obvious"
  | "appear"
  | "disappear"
  | "count_change"
  | "interval_sample"
  | "issue_frame"
  | "manual";

export interface ModelRequirements {
  api_key?: boolean | null;
  network?: boolean | null;
  gpu?: boolean | null;
  local_weights?: boolean | null;
}

export interface ModelRuntime {
  api_key_env?: string | null;
  api_url_env?: string | null;
  model_id_env?: string | null;
  confidence_env?: string | null;
}

export interface ModelMetrics {
  source?: string | null;
  scanned_image_count?: number | null;
  tested_count?: number | null;
  api_success_count?: number | null;
  images_with_detections?: number | null;
  total_detections?: number | null;
  confidence?: number | null;
}

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
  deployment_type?: ModelDeploymentType | null;
  provider?: string | null;
  task_types?: string[] | null;
  anatomy?: string[] | null;
  modality?: string[] | null;
  outputs?: string[] | null;
  requires?: ModelRequirements | null;
  runtime?: ModelRuntime | null;
  metrics?: ModelMetrics | null;
  limitations?: string[] | null;
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

export interface VideoUploadWarning {
  filename: string;
  message: string;
}

export interface VideoItem {
  id: string;
  dataset_id: string;
  patient_id: string | null;
  patient_uid: string | null;
  filename: string;
  file_path: string;
  file_url: string;
  duration_sec: number | null;
  fps: number | null;
  frame_count: number | null;
  width: number | null;
  height: number | null;
  preview_image_path: string | null;
  preview_image_url: string | null;
  lung_zone: string | null;
  probe: string | null;
  orientation: string | null;
  device: string | null;
  depth: string | null;
  deid_status: string;
  status: string;
  error_message: string | null;
  quality: VideoQuality;
  bline_grade: BLineGrade;
  uncertain_flag: boolean;
  include_in_training: boolean;
  review_comment: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  keyframe_count: number;
  created_at: string;
  updated_at: string;
}

export interface VideoDatasetUploadResponse {
  dataset_id: string;
  dataset_name: string;
  video_count: number;
  patient_count: number;
  videos: VideoItem[];
  warnings: VideoUploadWarning[];
}

export interface SplitSummaryItem {
  split: string;
  patient_count: number;
  video_count: number;
}

export interface ReviewSummaryItem {
  quality: string;
  count: number;
}

export interface VideoDatasetSummary {
  dataset_id: string;
  dataset_name: string;
  data_type: string;
  video_count: number;
  patient_count: number;
  keyframe_count: number;
  split_summary: SplitSummaryItem[];
  review_status_summary: ReviewSummaryItem[];
}

export interface VideoDatasetListItem {
  dataset_id: string;
  dataset_name: string;
  data_type: "video";
  task_type: "video_bline_segmentation";
  patient_count: number;
  video_count: number;
  keyframe_count: number;
  annotated_count: number;
  reviewed_count: number;
  updated_at: string;
}

export interface VideoDatasetListResponse {
  items: VideoDatasetListItem[];
  total: number;
}

export interface VideoListResponse {
  dataset_id: string;
  videos: VideoItem[];
  total: number;
}

export interface VideoReviewUpdateRequest {
  quality: VideoQuality;
  bline_grade: BLineGrade;
  uncertain_flag: boolean;
  include_in_training: boolean;
  comment?: string | null;
  reviewed_by?: string | null;
}

export interface VideoReview {
  video_id: string;
  quality: VideoQuality;
  bline_grade: BLineGrade;
  uncertain_flag: boolean;
  include_in_training: boolean;
  comment: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface KeyFrame {
  id: string;
  video_id: string;
  frame_index: number;
  timestamp_ms: number;
  selection_reason: KeyFrameReason;
  image_path: string;
  image_url: string;
  label_studio_project_id: number | null;
  label_studio_task_id: number | null;
  label_studio_task_url: string | null;
  annotation_status: string;
  review_status: string;
  annotation_updated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface KeyFrameExtractRequest {
  frame_indices?: number[];
  interval?: number;
  reasons?: KeyFrameReason[];
}

export interface KeyFrameExtractResponse {
  video_id: string;
  extracted_count: number;
  keyframes: KeyFrame[];
}

export interface KeyFrameListResponse {
  video_id: string;
  keyframes: KeyFrame[];
  total: number;
}

export interface KeyFrameLabelStudioInitRequest {
  keyframe_ids?: string[];
  project_title?: string | null;
}

export interface KeyFrameLabelStudioInitResponse {
  video_id: string;
  label_studio_project_id: number;
  label_studio_project_url: string;
  initialized_count: number;
  reused_count: number;
  keyframes: KeyFrame[];
}

export interface ReviewStatusSummaryItem {
  review_status: string;
  count: number;
}

export interface KeyFrameLabelStudioSyncResponse {
  video_id: string;
  total_keyframes: number;
  labeled_count: number;
  unlabeled_count: number;
  review_status_summary: ReviewStatusSummaryItem[];
  keyframes: KeyFrame[];
}

export interface VideoKeyframeExportResponse {
  export_id: string;
  dataset_id: string;
  total_labeled_count: number;
  skipped_count: number;
  file_path: string;
  download_url: string;
}
