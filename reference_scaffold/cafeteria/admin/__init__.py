from __future__ import annotations

# Complete the shared blueprint even when a caller imports one route module directly.
# Workflow routes also register print/review routes after defining their shared helpers.
from . import workflow_routes as workflow_routes
from . import api_routes as api_routes
from . import menu_collection_routes as menu_collection_routes
from . import week_management_routes as week_management_routes
from . import display_routes as display_routes
from . import branding_routes as branding_routes
from .routes import bp as bp
