from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from ..db import active_snapshot

bp = Blueprint('public', __name__)


def effective_today() -> dt.date:
    demo_today = current_app.config.get('DEMO_TODAY') if current_app.config.get('DEMO_MODE') else ''
    if demo_today:
        return dt.date.fromisoformat(demo_today)
    return dt.datetime.now(ZoneInfo('Europe/Zurich')).date()


def load_context(profile_code: str) -> dict:
    if 'date' in request.args:
        abort(400, description='Öffentliche Datumsparameter sind nicht erlaubt.')
    date_value = effective_today().isoformat()
    snapshot = active_snapshot(
        current_app.extensions['cafeteria_db'],
        profile_code,
        date_value,
        last_good_dir=current_app.config['LAST_GOOD_DIR'],
    )
    day = None
    if snapshot:
        day = next((item for item in snapshot.get('days', []) if item.get('date') == date_value), None)
    return {'snapshot': snapshot, 'day': day, 'today': date_value}


def service(day: dict | None, meal_code: str) -> dict | None:
    if not day:
        return None
    return next((item for item in day.get('services', []) if item.get('meal_code') == meal_code), None)


@bp.get('/')
def root():
    return redirect(url_for('public.cafeteria_today'))


@bp.get('/cafeteria/heute/')
def cafeteria_today():
    context = load_context('staff_guest')
    context['lunch'] = service(context['day'], 'LUNCH')
    return render_template('public/cafeteria_today.html', **context)


@bp.get('/cafeteria/wochenangebot/')
def cafeteria_week():
    context = load_context('staff_guest')
    context['open_days'] = [day for day in (context['snapshot'] or {}).get('days', []) if day.get('services')]
    return render_template('public/cafeteria_week.html', **context)


@bp.get('/patienten/heute/')
def patient_today():
    context = load_context('patient')
    context['lunch'] = service(context['day'], 'LUNCH')
    context['dinner'] = service(context['day'], 'DINNER')
    return render_template('public/patient_today.html', **context)


@bp.get('/patienten/wochenplan/')
def patient_week():
    return render_template('public/patient_week.html', **load_context('patient'))


@bp.get('/druck/cafeteria/woche')
def print_cafeteria_week():
    context = load_context('staff_guest')
    context['open_days'] = [day for day in (context['snapshot'] or {}).get('days', []) if day.get('services')]
    return render_template('public/print_cafeteria_week.html', **context)


@bp.get('/druck/patienten/woche')
def print_patient_week():
    return render_template('public/print_patient_week.html', **load_context('patient'))


@bp.get('/cafeteria/legende/')
def legend():
    return render_template('public/legend.html')
