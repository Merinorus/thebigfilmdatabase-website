# Project root directory
import os
from pathlib import Path

PROJECT_DIR = str(Path(os.path.dirname(__file__)).parent)

# Application directories. Used for module importation, tests...
APP_DIR = str(os.path.join(PROJECT_DIR, "app"))
STATIC_DIR = str(os.path.join(PROJECT_DIR, "static"))
TEMPLATE_DIR = str(os.path.join(PROJECT_DIR, "templates"))
