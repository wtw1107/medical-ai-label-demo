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


class ExportRecordStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(StrEnum):
    BBOX = "bbox"
    POLYGON = "polygon"
    BBOX_POLYGON = "bbox_polygon"


class DataType(StrEnum):
    IMAGE = "image"


class ExportFormat(StrEnum):
    LABEL_STUDIO_JSON = "label_studio_json"
    SIMPLE_JSON = "simple_json"
    COCO = "coco"
    YOLO = "yolo"
    MASK_PNG = "mask_png"


class ExportRange(StrEnum):
    CONFIRMED_ONLY = "confirmed_only"
    ALL = "all"


class PredictionStatus(StrEnum):
    NONE = "none"
    WRITTEN = "written"
    FAILED = "failed"


class AnnotationStatus(StrEnum):
    UNSAVED = "unsaved"
    SAVED = "saved"
