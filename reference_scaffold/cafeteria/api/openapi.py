from __future__ import annotations

from ..patient_payload import PATIENT_ALLERGEN_CODES, PATIENT_FIXED_VALUES, PATIENT_LABEL_CODES


def _enum_value(*path: str) -> list[str]:
    return sorted(PATIENT_FIXED_VALUES[path])


def build_openapi() -> dict:
    return {
        'openapi': '3.1.0',
        'info': {
            'title': 'Dishboard Menü-API',
            'version': '1.0.0',
            'description': 'Interne API für öffentliche Menüdaten.',
        },
        'servers': [{'url': '/'}],
        'tags': [
            {'name': 'published', 'description': 'Publizierte Menüpläne'},
            {'name': 'status', 'description': 'Systemstatus'},
            {'name': 'docs', 'description': 'Dokumentation'},
            {'name': 'weeks', 'description': 'Lesende Entwurfsvorschau'},
            {'name': 'keys', 'description': 'API-Schlüssel'},
        ],
        'paths': {
            '/api/v1/keys/me': {
                'get': {
                    'tags': ['keys'],
                    'summary': 'Identität des API-Schlüssels',
                    'security': [{'ApiKeyBearer': []}],
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/KeyIdentity'},
                                },
                            },
                        },
                        '401': {
                            'description': 'Nicht autorisiert',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Error'},
                                },
                            },
                        },
                    },
                },
            },
            '/api/v1/weeks/{channel}': {
                'get': {
                    'tags': ['weeks'],
                    'summary': 'Zwölf jüngste Wochen',
                    'security': [{'ApiKeyBearer': []}],
                    'parameters': [
                        {
                            'name': 'channel',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                        },
                    ],
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/WeeksResponse'},
                                },
                            },
                        },
                        '401': {
                            'description': 'Nicht autorisiert',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Error'},
                                },
                            },
                        },
                        '403': {
                            'description': 'Scope fehlt',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Error'},
                                },
                            },
                        },
                    },
                },
            },
            '/api/v1/weeks/{channel}/{date}/preview': {
                'get': {
                    'tags': ['weeks'],
                    'summary': 'Entwurf einer Woche im Snapshot-Format',
                    'security': [{'ApiKeyBearer': []}],
                    'parameters': [
                        {
                            'name': 'channel',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                        },
                        {
                            'name': 'date',
                            'in': 'path',
                            'required': True,
                            'description': 'Wochenbeginn (Montag)',
                            'schema': {'type': 'string', 'format': 'date'},
                        },
                    ],
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'headers': {
                                'X-Draft-Row-Version': {
                                    'schema': {'type': 'integer'},
                                },
                            },
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Snapshot'},
                                },
                            },
                        },
                        '400': {
                            'description': 'Ungültiger Wochenbeginn',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Error'},
                                },
                            },
                        },
                        '401': {
                            'description': 'Nicht autorisiert',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Error'},
                                },
                            },
                        },
                        '403': {
                            'description': 'Scope fehlt',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Error'},
                                },
                            },
                        },
                        '404': {
                            'description': 'Woche nicht gefunden',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Error'},
                                },
                            },
                        },
                    },
                },
            },
            '/api/v1/published/{channel}': {
                'get': {
                    'tags': ['published'],
                    'summary': 'Publizierter Kanal-Snapshot',
                    'parameters': [
                        {
                            'name': 'channel',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                        },
                    ],
                    'responses': {
                        '200': {'description': 'OK', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/DayResponse'}}}},
                        '404': {'description': 'Kein publiziertes Menü', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Error'}}}},
                    },
                },
            },
            '/api/v1/published/{channel}/today': {
                'get': {
                    'tags': ['published'],
                    'summary': 'Publizierter Tag für Heute',
                    'parameters': [
                        {
                            'name': 'channel',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                        },
                    ],
                    'responses': {
                        '200': {'description': 'OK', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/DayResponse'}}}},
                        '404': {'description': 'Kein publiziertes Menü', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Error'}}}},
                    },
                },
            },
            '/api/v1/published/{channel}/days/{date}': {
                'get': {
                    'tags': ['published'],
                    'summary': 'Publizierter Tag für Datum',
                    'parameters': [
                        {
                            'name': 'channel',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                        },
                        {
                            'name': 'date',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string', 'format': 'date'},
                        },
                    ],
                    'responses': {
                        '200': {'description': 'OK', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/DayResponse'}}}},
                        '400': {'description': 'Ungültiges Datum', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Error'}}}},
                        '404': {'description': 'Kein publiziertes Menü', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Error'}}}},
                    },
                },
            },
            '/api/v1/status': {
                'get': {
                    'tags': ['status'],
                    'summary': 'Systemstatus',
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Status'},
                                },
                            },
                        },
                    },
                },
            },
            '/api/v1/openapi.json': {
                'get': {
                    'tags': ['docs'],
                    'summary': 'OpenAPI-Dokument',
                    'responses': {
                        '200': {
                            'description': 'OpenAPI',
                            'content': {
                                'application/json': {
                                    'schema': {'type': 'object'},
                                },
                            },
                        },
                    },
                },
            },
            '/api/v1/docs': {
                'get': {
                    'tags': ['docs'],
                    'summary': 'Swagger UI',
                    'responses': {
                        '200': {
                            'description': 'Swagger-UI',
                            'content': {'text/html': {'schema': {'type': 'string'}}},
                        },
                    },
                },
            },
        },
        'components': {
            'securitySchemes': {
                'ApiKeyBearer': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'bearerFormat': 'dbk_…',
                },
            },
            'schemas': {
                'WeekSummary': {
                    'type': 'object',
                    'required': [
                        'week_start',
                        'week_end',
                        'title',
                        'workflow_state',
                        'status',
                    ],
                    'properties': {
                        'week_start': {'type': 'string', 'format': 'date'},
                        'week_end': {'type': 'string', 'format': 'date'},
                        'title': {'type': 'string'},
                        'workflow_state': {
                            'type': 'string',
                            'enum': ['draft', 'ready', 'published', 'archived'],
                        },
                        'status': {
                            'type': 'string',
                            'enum': ['empty', 'incomplete', 'review_open', 'live', 'changed', 'ready'],
                        },
                    },
                },
                'WeeksResponse': {
                    'type': 'object',
                    'required': ['channel', 'weeks'],
                    'properties': {
                        'channel': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                        'weeks': {
                            'type': 'array',
                            'items': {'$ref': '#/components/schemas/WeekSummary'},
                        },
                    },
                },
                'KeyIdentity': {
                    'type': 'object',
                    'required': ['label', 'scopes', 'expires_at', 'public_id'],
                    'properties': {
                        'label': {'type': 'string'},
                        'scopes': {
                            'type': 'array',
                            'items': {'type': 'string', 'enum': ['preview.read']},
                        },
                        'expires_at': {'type': ['string', 'null'], 'format': 'date-time'},
                        'public_id': {'type': 'string', 'format': 'uuid'},
                    },
                },
                'Snapshot': {
                    'type': 'object',
                    'required': [
                        'schema_version',
                        'profile_code',
                        'channel',
                        'revision_id',
                        'location',
                        'week_start',
                        'week_end',
                        'title',
                        'shared_note',
                        'days',
                    ],
                    'properties': {
                        'schema_version': {'type': 'integer', 'minimum': 1},
                        'profile_code': {'type': 'string', 'enum': ['patient', 'staff_guest']},
                        'channel': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                        'revision_id': {'type': ['string', 'null']},
                        'location': {'$ref': '#/components/schemas/Location'},
                        'week_start': {'type': 'string', 'format': 'date'},
                        'week_end': {'type': 'string', 'format': 'date'},
                        'title': {'type': 'string'},
                        'shared_note': {'type': 'string'},
                        'days': {'type': 'array', 'items': {'$ref': '#/components/schemas/Day'}},
                    },
                },
                'Location': {
                    'type': 'object',
                    'required': ['code', 'name'],
                    'properties': {'code': {'type': 'string'}, 'name': {'type': 'string'}},
                },
                'Day': {
                    'type': 'object',
                    'required': ['date', 'weekday', 'state', 'notice', 'services'],
                    'properties': {
                        'date': {'type': 'string', 'format': 'date'},
                        'weekday': {'type': 'string', 'enum': _enum_value('day', 'weekday')},
                        'state': {'type': 'string', 'enum': _enum_value('day', 'state')},
                        'notice': {'type': 'string'},
                        'services': {'type': 'array', 'items': {'$ref': '#/components/schemas/Service'}},
                    },
                },
                'Service': {
                    'type': 'object',
                    'required': ['meal_code', 'meal_name', 'options'],
                    'properties': {
                        'meal_code': {'type': 'string', 'enum': _enum_value('service', 'meal_code')},
                        'meal_name': {'type': 'string', 'enum': _enum_value('service', 'meal_name')},
                        'service_state': {'type': 'string', 'enum': _enum_value('service', 'service_state')},
                        'notice': {'type': 'string'},
                        'options': {'type': 'array', 'items': {'$ref': '#/components/schemas/Option'}},
                    },
                },
                'Option': {
                    'type': 'object',
                    'required': [
                        'external_id',
                        'type_code',
                        'type_name',
                        'title',
                        'description',
                        'components',
                        'labels',
                        'allergens',
                        'origins',
                        'note',
                        'allergen_review_status',
                    ],
                    'properties': {
                        'external_id': {'type': 'string'},
                        'type_code': {'type': 'string', 'enum': _enum_value('option', 'type_code')},
                        'type_name': {'type': 'string', 'enum': _enum_value('option', 'type_name')},
                        'title': {'type': 'string'},
                        'description': {'type': 'string'},
                        'components': {'type': 'array', 'items': {'type': 'string'}},
                        'labels': {'type': 'array', 'items': {'$ref': '#/components/schemas/Label'}},
                        'allergens': {'type': 'array', 'items': {'$ref': '#/components/schemas/Allergen'}},
                        'origins': {'type': 'array', 'items': {'$ref': '#/components/schemas/Origin'}},
                        'note': {'type': 'string'},
                        'allergen_review_status': {'type': 'string', 'enum': _enum_value('option', 'allergen_review_status')},
                        'prices': {
                            'type': 'object',
                            'description': 'Cafeteria-Optionen: nur im Staff-Kanal gesetzt.',
                            '$ref': '#/components/schemas/Prices',
                        },
                    },
                },
                'Prices': {
                    'type': 'object',
                    'required': ['internal_rappen', 'external_rappen'],
                    'properties': {
                        'internal_rappen': {'type': 'integer', 'minimum': 0},
                        'external_rappen': {'type': 'integer', 'minimum': 0},
                        'currency': {'type': 'string', 'enum': ['CHF']},
                    },
                },
                'Label': {
                    'type': 'object',
                    'required': ['code', 'name'],
                    'properties': {
                        'code': {'type': 'string', 'enum': sorted(PATIENT_LABEL_CODES)},
                        'name': {'type': 'string'},
                    },
                },
                'Allergen': {
                    'type': 'object',
                    'required': ['code', 'name', 'presence'],
                    'properties': {
                        'code': {'type': 'string', 'enum': sorted(PATIENT_ALLERGEN_CODES)},
                        'name': {'type': 'string'},
                        'presence': {'type': 'string', 'enum': ['contains', 'may_contain']},
                    },
                },
                'Origin': {
                    'type': 'object',
                    'required': ['ingredient', 'country_code', 'text'],
                    'properties': {
                        'ingredient': {'type': 'string'},
                        'country_code': {'type': 'string'},
                        'text': {'type': 'string'},
                    },
                },
                'DayResponse': {
                    'allOf': [
                        {'$ref': '#/components/schemas/Snapshot'},
                        {
                            'type': 'object',
                            'required': ['channel', 'profile_code', 'revision_id', 'date', 'day'],
                            'properties': {
                                'channel': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                                'profile_code': {'type': 'string', 'enum': ['staff_guest', 'patient']},
                                'revision_id': {'type': ['string', 'null']},
                                'date': {'type': 'string', 'format': 'date'},
                                'day': {'$ref': '#/components/schemas/Day'},
                            },
                        },
                    ],
                },
                'Status': {
                    'type': 'object',
                    'required': ['service', 'api_version', 'time', 'channels', 'fhir', 'docs'],
                    'properties': {
                        'service': {'type': 'string', 'enum': ['dishboard']},
                        'api_version': {'type': 'string'},
                        'time': {'type': 'string', 'format': 'date-time'},
                        'channels': {'type': 'array', 'items': {'$ref': '#/components/schemas/ChannelStatus'}},
                        'fhir': {
                            'type': 'object',
                            'required': ['version', 'base_path', 'metadata'],
                            'properties': {
                                'version': {'type': 'string'},
                                'base_path': {'type': 'string'},
                                'metadata': {'type': 'string'},
                            },
                        },
                        'docs': {
                            'type': 'object',
                            'required': ['openapi', 'swagger_ui'],
                            'properties': {
                                'openapi': {'type': 'string'},
                                'swagger_ui': {'type': 'string'},
                            },
                        },
                    },
                },
                'ChannelStatus': {
                    'type': 'object',
                    'required': [
                        'channel',
                        'profile_code',
                        'published',
                        'revision_id',
                        'week_start',
                        'week_end',
                        'today_state',
                    ],
                    'properties': {
                        'channel': {'type': 'string', 'enum': ['cafeteria', 'patienten']},
                        'profile_code': {'type': 'string', 'enum': ['staff_guest', 'patient']},
                        'published': {'type': 'boolean'},
                        'revision_id': {'type': ['string', 'null']},
                        'week_start': {'type': ['string', 'null'], 'format': 'date'},
                        'week_end': {'type': ['string', 'null'], 'format': 'date'},
                        'today_state': {'type': ['string', 'null'], 'enum': _enum_value('day', 'state')},
                    },
                },
                'Error': {
                    'type': 'object',
                    'required': ['error', 'detail'],
                    'properties': {
                        'error': {'type': 'string'},
                        'detail': {'type': 'string'},
                    },
                },
            },
        },
    }
