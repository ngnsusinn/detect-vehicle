"""Canonical class IDs. Exported annotations must be remapped to this order."""
CLASS_NAMES = (
    "motorcycle", "car", "electric_bicycle", "bicycle", "bus", "truck",
    "container_truck", "special_vehicle",
)
VEHICLE_CLASSES = dict(enumerate(CLASS_NAMES))
CLASS_NAMES_VI = {
    "motorcycle": "Xe máy",
    "car": "Ô tô con",
    "electric_bicycle": "Xe đạp điện",
    "bicycle": "Xe đạp",
    "bus": "Xe khách/buýt",
    "truck": "Xe tải",
    "container_truck": "Xe container",
    "special_vehicle": "Xe chuyên dụng",
}
