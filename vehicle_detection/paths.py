"""Default locations anchored to the checkout, independent of the working directory."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_FRAMES_DIR = DATA_DIR / "raw" / "frames"
ANNOTATION_BATCHES_DIR = DATA_DIR / "annotation_batches"
DATASET_DIR = DATA_DIR / "vehicle_detection"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
