from enum import Enum, StrEnum


class DatasetStatus(StrEnum):
    UPLOADED = "uploaded"
    READY = "ready"
    ERROR = "error"


class ImageStatus(StrEnum):
    UPLOADED = "uploaded"
    PRELABELING = "prelabeling"
    PRELABEL_DONE = "prelabel_done"
    PRELABEL_FAILED = "prelabel_failed"
    CONFIRMED = "confirmed"
    IGNORED = "ignored"


class AnnotationTaskStatus(StrEnum):
    CREATED = "created"
    PRELABELING = "prelabeling"
    REVIEWING = "reviewing"
    EXPORTABLE = "exportable"
    EXPORTED = "exported"
    ERROR = "error"


class PrelabelJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL_FAILED = "partial_failed"


class LabelStudioFieldName(StrEnum):
    IMAGE = "image"
    BBOX = "bbox"
    LESION_POLYGON = "lesion_polygon"
    BLINE_POLYGON = "bline_polygon"
    REVIEW_STATUS = "review_status"
    REVIEW_COMMENT = "review_comment"
    UNCERTAIN_FLAG = "uncertain_flag"


class ExportRecordStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(StrEnum):
    BBOX = "bbox"
    POLYGON = "polygon"
    BBOX_POLYGON = "bbox_polygon"
    VIDEO_BLINE_SEGMENTATION = "video_bline_segmentation"


class DataType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class ExportFormat(StrEnum):
    LABEL_STUDIO_JSON = "label_studio_json"
    SIMPLE_JSON = "simple_json"
    COCO = "coco"
    YOLO = "yolo"
    MASK_PNG = "mask_png"


class ExportRange(StrEnum):
    CONFIRMED_ONLY = "confirmed_only"
    ALL = "all"


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VAL = "val"
    TEST = "test"
    UNASSIGNED = "unassigned"


class VideoQuality(StrEnum):
    GOOD = "good"
    USABLE = "usable"
    POOR = "poor"
    UNKNOWN = "unknown"


class BLineGrade(StrEnum):
    ZERO = "0"
    ONE_TO_TWO = "1-2"
    THREE_PLUS = "3+"
    CONFLUENT = "confluent"
    UNKNOWN = "unknown"


class DeidentificationStatus(StrEnum):
    UNKNOWN = "unknown"
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class VideoItemStatus(StrEnum):
    UPLOADED = "uploaded"
    READY = "ready"
    ERROR = "error"


class KeyFrameReason(StrEnum):
    FIRST_CLEAR = "first_clear"
    MOST_OBVIOUS = "most_obvious"
    APPEAR = "appear"
    DISAPPEAR = "disappear"
    COUNT_CHANGE = "count_change"
    INTERVAL_SAMPLE = "interval_sample"
    ISSUE_FRAME = "issue_frame"
    MANUAL = "manual"


class VideoAnnotationStatus(StrEnum):
    PENDING = "pending"
    ANNOTATED = "annotated"
    SKIPPED = "skipped"


class KeyFrameReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"


class PredictionStatus(StrEnum):
    NONE = "none"
    WRITTEN = "written"
    FAILED = "failed"


class AnnotationStatus(StrEnum):
    UNSAVED = "unsaved"
    SAVED = "saved"
