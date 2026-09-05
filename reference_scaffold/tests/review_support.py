"""Explicit review actions for publication fixtures; never migrate stored approvals."""
from sqlalchemy import text

from cafeteria.component_catalog_store import AdminScope
from cafeteria.workflow_review import get_component_review_token, review_component
from cafeteria.workflow_review_context import get_week_review, review_week_context


def review_saved_week(engine, profile, week, actor):
    with engine.connect() as connection:
        location = connection.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one()
        items = connection.execute(text('''
            SELECT i.id,i.row_version FROM cafeteria.menu_items i
            JOIN cafeteria.menu_services s ON s.id=i.service_id
            JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
            JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            WHERE w.location_id=:location AND p.code=:profile AND w.week_start=:week
              AND i.allergen_review_status='checked' ORDER BY i.id
        '''), {'location': location, 'profile': profile, 'week': week}).all()
    scope = AdminScope(actor, location, profile)
    for item in items:
        token = get_component_review_token(engine, scope, item.id)
        review_component(engine, scope, item.id, token, item.row_version)
    context = get_week_review(engine, scope, week)
    if context['receipt'] is None:
        review_week_context(engine, scope, week, context['token'])
    with engine.connect() as connection:
        return connection.execute(text('''
            SELECT w.row_version FROM cafeteria.menu_weeks w
            JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            WHERE w.location_id=:location AND p.code=:profile AND w.week_start=:week
        '''), {'location': location, 'profile': profile, 'week': week}).scalar_one()
