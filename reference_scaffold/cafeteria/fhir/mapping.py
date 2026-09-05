from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo


def system_uri(base_url: str, kind: str, name: str) -> str:
    return f"{base_url}/fhir/{kind}/{name}"


def product_id(external_id: str) -> str:
    return external_id.replace('_', '-')


def nutrition_product(snapshot: dict, day: dict, service: dict, option: dict, *, base_url: str) -> dict:
    ext_id = option['external_id']
    resource_id = product_id(ext_id)

    resource: dict[str, Any] = {
        "resourceType": "NutritionProduct",
        "id": resource_id,
        "identifier": [{
            "system": system_uri(base_url, "identifier", "menu-option"),
            "value": ext_id
        }],
        "status": "active",
        "category": [{
            "coding": [{
                "system": system_uri(base_url, "CodeSystem", "menu-type"),
                "code": option['type_code'],
                "display": option['type_name']
            }]
        }],
        "code": {
            "text": option['title']
        }
    }

    notes = []
    if option.get('description'):
        notes.append({"text": option['description']})
    if option.get('note'):
        notes.append({"text": option['note']})
    if notes:
        resource["note"] = notes

    ingredients = []
    for comp in option.get('components', []):
        ingredients.append({
            "item": {
                "concept": {
                    "text": comp
                }
            }
        })
    if ingredients:
        resource["ingredient"] = ingredients

    known_allergens = []
    for alg in option.get('allergens', []):
        known_allergens.append({
            "extension": [{
                "url": system_uri(base_url, "StructureDefinition", "allergen-presence"),
                "valueCode": alg['presence']
            }],
            "concept": {
                "coding": [{
                    "system": system_uri(base_url, "CodeSystem", "allergen"),
                    "code": alg['code'],
                    "display": alg['name']
                }]
            }
        })
    if known_allergens:
        resource["knownAllergen"] = known_allergens

    characteristics = []
    for label in option.get('labels', []):
        characteristics.append({
            "type": {
                "coding": [{
                    "system": system_uri(base_url, "CodeSystem", "dietary-label"),
                    "code": label['code'],
                    "display": label['name']
                }]
            },
            "valueBoolean": True
        })

    characteristics.append({
        "type": {
            "coding": [{
                "system": system_uri(base_url, "CodeSystem", "menu-characteristic"),
                "code": "service-date"
            }]
        },
        "valueString": day['date']
    })

    characteristics.append({
        "type": {
            "coding": [{
                "system": system_uri(base_url, "CodeSystem", "meal")
            }]
        },
        "valueCodeableConcept": {
            "coding": [{
                "system": system_uri(base_url, "CodeSystem", "meal"),
                "code": service['meal_code'],
                "display": service['meal_name']
            }]
        }
    })

    characteristics.append({
        "type": {
            "coding": [{
                "system": system_uri(base_url, "CodeSystem", "channel")
            }]
        },
        "valueCodeableConcept": {
            "coding": [{
                "system": system_uri(base_url, "CodeSystem", "channel"),
                "code": snapshot['channel']
            }]
        }
    })

    if option.get('allergen_review_status'):
        characteristics.append({
            "type": {
                "coding": [{
                    "system": system_uri(base_url, "CodeSystem", "allergen-review")
                }]
            },
            "valueCodeableConcept": {
                "coding": [{
                    "system": system_uri(base_url, "CodeSystem", "allergen-review"),
                    "code": option['allergen_review_status']
                }]
            }
        })

    for origin in option.get('origins', []):
        characteristics.append({
            "type": {
                "coding": [{
                    "system": system_uri(base_url, "CodeSystem", "origin")
                }]
            },
            "valueString": origin['text']
        })

    resource["characteristic"] = characteristics

    prices = option.get('prices')
    if prices and snapshot.get('profile_code') == 'staff_guest':
        exts = []
        if 'internal_rappen' in prices:
            exts.append({
                "url": system_uri(base_url, "StructureDefinition", "menu-price"),
                "extension": [
                    {"url": "audience", "valueCode": "internal"},
                    {"url": "amount", "valueMoney": {"value": prices['internal_rappen'] / 100, "currency": "CHF"}}
                ]
            })
        if 'external_rappen' in prices:
            exts.append({
                "url": system_uri(base_url, "StructureDefinition", "menu-price"),
                "extension": [
                    {"url": "audience", "valueCode": "external"},
                    {"url": "amount", "valueMoney": {"value": prices['external_rappen'] / 100, "currency": "CHF"}}
                ]
            })
        if exts:
            resource["extension"] = exts

    return resource


def nutrition_products(snapshot: dict, *, base_url: str) -> list[dict]:
    products = []
    for day in snapshot.get('days', []):
        for service in day.get('services', []):
            if service.get('service_state', 'open') == 'open':
                for option in service.get('options', []):
                    products.append(nutrition_product(snapshot, day, service, option, base_url=base_url))
    return products


def composition(snapshot: dict, *, base_url: str) -> dict:
    loc_name = snapshot.get('location', {}).get('name', '')
    title = f"{snapshot.get('title', '')} – {loc_name}"

    resource: dict[str, Any] = {
        "resourceType": "Composition",
        "id": snapshot['revision_id'],
        "identifier": [{
            "system": system_uri(base_url, "identifier", "publication-revision"),
            "value": snapshot['revision_id']
        }],
        "status": "final",
        "type": {
            "coding": [{
                "system": system_uri(base_url, "CodeSystem", "document-type"),
                "code": "menu-plan",
                "display": "Wochenmenüplan"
            }]
        },
        "date": snapshot['week_start'],
        "title": title,
        "author": [{"display": loc_name}],
        "custodian": {"display": loc_name},
        "event": [{
            "period": {
                "start": snapshot['week_start'],
                "end": snapshot['week_end']
            }
        }],
        "extension": [
            {
                "url": system_uri(base_url, "StructureDefinition", "menu-channel"),
                "valueCode": snapshot['channel']
            }
        ]
    }

    if snapshot.get('shared_note'):
        resource["extension"].append({
            "url": system_uri(base_url, "StructureDefinition", "shared-note"),
            "valueString": snapshot['shared_note']
        })

    sections = []
    for day in snapshot.get('days', []):
        day_date = day['date']
        weekday = day['weekday']
        section_title = f"{weekday} {day_date}"

        day_section: dict[str, Any] = {
            "title": section_title,
            "code": {"text": weekday}
        }

        services = day.get('services', [])
        if not services:
            day_section["emptyReason"] = {"text": day.get('notice') or "geschlossen"}
        else:
            subsections = []
            for svc in services:
                svc_section: dict[str, Any] = {
                    "title": svc['meal_name']
                }
                if svc.get('service_state', 'open') != 'open':
                    svc_section["emptyReason"] = {"text": svc.get('notice') or day.get('notice') or "geschlossen"}
                else:
                    entries = []
                    for opt in svc.get('options', []):
                        pid = product_id(opt['external_id'])
                        entries.append({
                            "reference": f"NutritionProduct/{pid}",
                            "display": opt['title']
                        })
                    svc_section["entry"] = entries
                subsections.append(svc_section)
            day_section["section"] = subsections

        sections.append(day_section)

    resource["section"] = sections
    return resource


def document_bundle(snapshot: dict, *, base_url: str) -> dict:
    comp = composition(snapshot, base_url=base_url)

    entries = []
    entries.append({
        "fullUrl": system_uri(base_url, "Composition", comp["id"]),
        "resource": comp
    })

    products = nutrition_products(snapshot, base_url=base_url)
    for prod in products:
        entries.append({
            "fullUrl": system_uri(base_url, "NutritionProduct", prod["id"]),
            "resource": prod
        })

    return {
        "resourceType": "Bundle",
        "type": "document",
        "identifier": comp["identifier"],
        "timestamp": dt.datetime.now(ZoneInfo("Europe/Zurich")).isoformat(timespec='seconds'),
        "entry": entries
    }


def searchset_bundle(resources: list[dict], *, base_url: str, self_url: str) -> dict:
    entries = []
    for res in resources:
        entries.append({
            "fullUrl": system_uri(base_url, res["resourceType"], res["id"]),
            "resource": res,
            "search": {"mode": "match"}
        })
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(resources),
        "link": [{"relation": "self", "url": self_url}],
        "entry": entries
    }


def capability_statement(*, base_url: str, software_version: str, now: str) -> dict:
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": now,
        "kind": "instance",
        "fhirVersion": "5.0.0",
        "format": ["json"],
        "software": {
            "name": "Dishboard",
            "version": software_version
        },
        "implementation": {
            "description": "Dishboard Menüplanung Klinik Südhang",
            "url": base_url + "/fhir"
        },
        "rest": [{
            "mode": "server",
            "resource": [
                {
                    "type": "NutritionProduct",
                    "interaction": [{"code": "read"}, {"code": "search-type"}],
                    "searchParam": [
                        {"name": "channel", "type": "token"},
                        {"name": "date", "type": "date"}
                    ]
                },
                {
                    "type": "Composition",
                    "interaction": [{"code": "read"}, {"code": "search-type"}],
                    "searchParam": [
                        {"name": "channel", "type": "token"}
                    ],
                    "operation": [{
                        "name": "document",
                        "definition": "http://hl7.org/fhir/OperationDefinition/Composition-document"
                    }]
                }
            ]
        }]
    }


def operation_outcome(severity: str, code: str, diagnostics: str) -> dict:
    return {
        "resourceType": "OperationOutcome",
        "issue": [{
            "severity": severity,
            "code": code,
            "diagnostics": diagnostics
        }]
    }
