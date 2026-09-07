from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from ..db import active_snapshot
from ..screen_templates import ScreenStateError, read_assignment
from ..template_filters import cafeteria_visible_days, weekday_range_label

bp = Blueprint('public', __name__)

PUBLIC_CACHE_CONTROL = 'public, max-age=60, stale-if-error=86400'


def no_store_failure(message: str, status_code: int):
    response = make_response(render_template('public/unavailable.html'), status_code)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.before_request
def reject_query_parameters():
    if request.query_string:
        return no_store_failure('Öffentliche Query-Parameter sind nicht erlaubt.', 400)
    return None


def effective_today() -> dt.date:
    demo_today = current_app.config.get('DEMO_TODAY') if current_app.config.get('DEMO_MODE') else ''
    if demo_today:
        return dt.date.fromisoformat(demo_today)
    return dt.datetime.now(ZoneInfo('Europe/Zurich')).date()


def published_snapshot(profile_code: str) -> dict | None:
    try:
        return active_snapshot(
            current_app.extensions['cafeteria_db'],
            profile_code,
            effective_today().isoformat(),
            last_good_dir=current_app.config['LAST_GOOD_DIR'],
        )
    except ValueError:
        return None


def load_context(profile_code: str) -> dict:
    date_value = effective_today().isoformat()
    snapshot = published_snapshot(profile_code)
    day = None
    if snapshot:
        day = next((item for item in snapshot.get('days', []) if item.get('date') == date_value), None)
    return {
        'snapshot': snapshot, 'day': day, 'today': date_value,
        'area_name': (snapshot or {}).get('area_name', ''),
    }


def cafeteria_context() -> dict:
    """Cafeteria pages name the days they show, weekends only when a service is open."""
    context = load_context('staff_guest')
    context['open_days'] = cafeteria_visible_days((context['snapshot'] or {}).get('days', []))
    context['weekday_range'] = weekday_range_label(context['open_days'])
    return context


def service(day: dict | None, meal_code: str) -> dict | None:
    if not day:
        return None
    return next((item for item in day.get('services', []) if item.get('meal_code') == meal_code), None)


def published_response(template: str, context: dict):
    snapshot = context['snapshot']
    if not snapshot:
        return no_store_failure('Kein publizierter Menüplan für diesen Kanal.', 404)
    response = make_response(render_template(template, **context))
    response.headers['Cache-Control'] = PUBLIC_CACHE_CONTROL
    response.headers['X-Snapshot-Revision'] = snapshot['revision_id']
    return response


@bp.get('/')
def root():
    return redirect(url_for('public.cafeteria_today'))


@bp.get('/cafeteria/heute/')
def cafeteria_today():
    context = cafeteria_context()
    context['lunch'] = service(context['day'], 'LUNCH')
    return published_response('public/cafeteria_today.html', context)


@bp.get('/cafeteria/wochenangebot/ohne-bilder/', endpoint='cafeteria_week_without_images',
        defaults={'show_menu_images': False})
@bp.get('/cafeteria/wochenangebot/')
def cafeteria_week(show_menu_images: bool = True):
    explicit_without_images = not show_menu_images
    assignment = None
    if show_menu_images:
        try:
            with current_app.extensions['cafeteria_db'].connect() as connection:
                assignment = read_assignment(connection, 'staff_guest')
            show_menu_images = assignment.template.show_menu_images
        except (SQLAlchemyError, ScreenStateError):
            response = make_response(current_app.jinja_env.get_template('admin/screen_template_unavailable.html').render(), 503)
            response.headers['Cache-Control'] = 'no-store'
            return response
    context = cafeteria_context()
    context['show_menu_images'] = show_menu_images
    context['explicit_without_images'] = explicit_without_images
    response = published_response('public/cafeteria_week.html', context)
    if assignment is not None:
        response.headers['X-Screen-Template-Revision'] = assignment.revision
        response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/patienten/heute/')
def patient_today():
    context = load_context('patient')
    context['lunch'] = service(context['day'], 'LUNCH')
    context['dinner'] = service(context['day'], 'DINNER')
    return published_response('public/patient_today.html', context)


@bp.get('/patienten/wochenplan/ohne-bilder/', endpoint='patient_week_without_images',
        defaults={'show_menu_images': False})
@bp.get('/patienten/wochenplan/')
def patient_week(show_menu_images: bool = True):
    explicit_without_images = not show_menu_images
    assignment = None
    if show_menu_images:
        try:
            with current_app.extensions['cafeteria_db'].connect() as connection:
                assignment = read_assignment(connection, 'patient')
            show_menu_images = assignment.template.show_menu_images
        except (SQLAlchemyError, ScreenStateError):
            response = make_response(current_app.jinja_env.get_template('admin/screen_template_unavailable.html').render(), 503)
            response.headers['Cache-Control'] = 'no-store'
            return response
    context = load_context('patient')
    context['show_menu_images'] = show_menu_images
    context['explicit_without_images'] = explicit_without_images
    response = published_response('public/patient_week.html', context)
    if assignment is not None:
        response.headers['X-Screen-Template-Revision'] = assignment.revision
        response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/druck/cafeteria/woche')
def print_cafeteria_week():
    return published_response('public/print_cafeteria_week.html', cafeteria_context())


@bp.get('/druck/patienten/woche')
def print_patient_week():
    return published_response('public/print_patient_week.html', load_context('patient'))


@bp.get('/cafeteria/legende/')
def legend():
    return render_template('public/legend.html')
