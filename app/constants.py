# Project root directory
import os
from pathlib import Path

PROJECT_DIR = str(Path(os.path.dirname(__file__)).parent)

# Application directories. Used for module importation, tests...
APP_DIR = str(os.path.join(PROJECT_DIR, "app"))
STATIC_DIR = str(os.path.join(PROJECT_DIR, "static"))
TEMPLATE_DIR = str(os.path.join(PROJECT_DIR, "templates"))

# URLS
STATIC_DIR_URL = "/static/"
FILM_IMAGE_DIR_URL = "/film-images/"
