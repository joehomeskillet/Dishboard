from __future__ import annotations

# Complete the shared blueprint even when a caller imports one route module directly.
# Workflow routes also register print/review routes after defining their shared helpers.
from . import workflow_routes as workflow_routes
from . import api_routes as api_routes
from . import menu_collection_routes as menu_collection_routes
from . import week_management_routes as week_management_routes
from . import display_routes as display_routes
from . import operations_routes as operations_routes
from . import branding_routes as branding_routes
from . import local_user_routes as local_user_routes
from . import master_data_routes as master_data_routes
from . import screen_template_routes as screen_template_routes
from . import recipe_routes as recipe_routes
from . import recipe_revision_routes as recipe_revision_routes
from . import recipe_image_routes as recipe_image_routes
from . import cookbook_routes as cookbook_routes
from ..roles import capabilities
from .routes import bp as bp
from .rendering import _template_context

# Also supplies direct render_template consumers such as the copy form.
bp.context_processor(_template_context)


@bp.context_processor
def recipe_navigation_context() -> dict[str, bool]:
    allowed = capabilities()
    return {'can_browse_recipes': bool(allowed & {'*', 'draft.read'})}
