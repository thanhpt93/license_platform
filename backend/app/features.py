"""
Defines the authoritative list of software features for NOVA Machine Vision Platform.
At this stage (Phase 1), creating a license defaults to granting all software features (*).
"""
from typing import List

ALL_SOFTWARE_FEATURES: List[str] = [
    "*",
    "anomaly_detection",
    "barcode_reader",
    "blob_analysis",
    "camera_calibration",
    "contour_detection",
    "deep_learning_ocr",
    "ethercat_trigger_bridge",
    "high_speed_acquisition",
    "measurement_metrology",
    "mqtt_publisher",
    "multi_camera_sync",
    "offline_simulator",
    "pipeline_studio",
    "plc_modbus_profinet",
    "qr_reader",
    "shape_analysis",
    "spc_telemetry_export",
    "surface_defect_detection",
    "tcp_ip_stream",
    "template_matching",
]


def get_default_features() -> List[str]:
    """Returns a fresh copy of all software features for default license entitlements."""
    return list(ALL_SOFTWARE_FEATURES)


def is_all_features_entitlement(features: List[str]) -> bool:
    """Returns True if the feature list represents full/unrestricted feature access."""
    if not features:
        return True
    if "*" in features or "all" in [str(f).lower() for f in features]:
        return True
    return set(ALL_SOFTWARE_FEATURES).issubset(set(features))
