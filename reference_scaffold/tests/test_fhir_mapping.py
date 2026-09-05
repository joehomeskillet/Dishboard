import json
import sys
from pathlib import Path
import datetime as dt
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from demo_snapshots import cafeteria_snapshot, patient_snapshot
from cafeteria.fhir import mapping

BASE_URL = "http://localhost:8080"


def test_product_count_and_id_rule():
    caf_products = mapping.nutrition_products(cafeteria_snapshot(), base_url=BASE_URL)
    assert len(caf_products) == 10

    pat_products = mapping.nutrition_products(patient_snapshot(), base_url=BASE_URL)
    assert len(pat_products) == 28
    
    for prod in caf_products + pat_products:
        assert '_' not in prod['id']
        assert '-' in prod['id']


def test_allergen_and_label_coding():
    caf_products = mapping.nutrition_products(cafeteria_snapshot(), base_url=BASE_URL)
    product_with_allergens = next(p for p in caf_products if p.get('knownAllergen'))
    
    allergen = product_with_allergens['knownAllergen'][0]
    assert allergen['extension'][0]['url'] == f"{BASE_URL}/fhir/StructureDefinition/allergen-presence"
    assert allergen['extension'][0]['valueCode'] in ['contains', 'may_contain']
    
    coding = allergen['concept']['coding'][0]
    assert coding['system'] == f"{BASE_URL}/fhir/CodeSystem/allergen"
    assert 'code' in coding
    assert 'display' in coding
    
    product_with_labels = next(p for p in caf_products if any(
        c.get('type', {}).get('coding', [{}])[0].get('system') == f"{BASE_URL}/fhir/CodeSystem/dietary-label"
        for c in p.get('characteristic', [])
    ))
    labels = [
        c for c in product_with_labels['characteristic']
        if c.get('type', {}).get('coding', [{}])[0].get('system') == f"{BASE_URL}/fhir/CodeSystem/dietary-label"
    ]
    assert labels
    assert labels[0]['valueBoolean'] is True


def test_characteristics():
    caf_products = mapping.nutrition_products(cafeteria_snapshot(), base_url=BASE_URL)
    prod = caf_products[0]
    
    chars = prod.get('characteristic', [])
    
    service_date = next(c for c in chars if c['type']['coding'][0]['code'] == 'service-date')
    assert service_date['valueString']
    
    meal = next(c for c in chars if c['type']['coding'][0].get('system') == f"{BASE_URL}/fhir/CodeSystem/meal")
    assert meal['valueCodeableConcept']['coding'][0]['code'] in ['LUNCH', 'DINNER']
    
    channel = next(c for c in chars if c['type']['coding'][0].get('system') == f"{BASE_URL}/fhir/CodeSystem/channel")
    assert channel['valueCodeableConcept']['coding'][0]['code'] == 'cafeteria'


def test_price_extensions():
    caf_products = mapping.nutrition_products(cafeteria_snapshot(), base_url=BASE_URL)
    pat_products = mapping.nutrition_products(patient_snapshot(), base_url=BASE_URL)
    
    # Preis-Extensions nur bei Cafeteria
    for prod in caf_products:
        exts = prod.get('extension', [])
        price_exts = [e for e in exts if e['url'] == f"{BASE_URL}/fhir/StructureDefinition/menu-price"]
        assert len(price_exts) == 2
        
    for prod in pat_products:
        exts = prod.get('extension', [])
        price_exts = [e for e in exts if e['url'] == f"{BASE_URL}/fhir/StructureDefinition/menu-price"]
        assert len(price_exts) == 0


def test_composition_sections():
    comp = mapping.composition(cafeteria_snapshot(), base_url=BASE_URL)
    sections = comp.get('section', [])
    assert len(sections) == 7
    
    # Cafeteria Wochenende
    weekend = [s for s in sections if s['code']['text'] in ['Samstag', 'Sonntag']]
    for day in weekend:
        assert 'emptyReason' in day
        assert 'section' not in day
        
    pat_comp = mapping.composition(patient_snapshot(), base_url=BASE_URL)
    pat_sections = pat_comp.get('section', [])
    assert len(pat_sections) == 7
    for day in pat_sections:
        assert 'section' in day


def test_document_bundle():
    bundle = mapping.document_bundle(cafeteria_snapshot(), base_url=BASE_URL)
    assert bundle['resourceType'] == 'Bundle'
    assert bundle['type'] == 'document'
    
    entries = bundle['entry']
    assert len(entries) == 1 + 10  # Composition + 10 products
    
    assert entries[0]['resource']['resourceType'] == 'Composition'
    assert entries[0]['fullUrl'] == f"{BASE_URL}/fhir/Composition/{entries[0]['resource']['id']}"
    
    assert entries[1]['resource']['resourceType'] == 'NutritionProduct'
    assert entries[1]['fullUrl'] == f"{BASE_URL}/fhir/NutritionProduct/{entries[1]['resource']['id']}"


def test_capability_statement():
    now = dt.datetime.now(ZoneInfo('Europe/Zurich')).isoformat()
    cap = mapping.capability_statement(base_url=BASE_URL, software_version='1.0', now=now)
    assert cap['status'] == 'active'
    assert cap['fhirVersion'] == '5.0.0'
    assert cap['software']['version'] == '1.0'
    
    rest = cap['rest'][0]
    assert rest['mode'] == 'server'
    resources = {r['type']: r for r in rest['resource']}
    
    assert 'NutritionProduct' in resources
    assert 'Composition' in resources
    
    comp_ops = resources['Composition'].get('operation', [])
    assert comp_ops[0]['name'] == 'document'


def test_patient_rule():
    pat_products = mapping.nutrition_products(patient_snapshot(), base_url=BASE_URL)
    pat_comp = mapping.composition(patient_snapshot(), base_url=BASE_URL)
    pat_bundle = mapping.document_bundle(patient_snapshot(), base_url=BASE_URL)
    
    resources_to_test = pat_products + [pat_comp, pat_bundle]
    
    forbidden_terms = ['preis', 'price', 'chf', 'rappen', 'kosten', 'money', 'currency', 'intern', 'extern', '0.00']
    
    for res in resources_to_test:
        json_str = json.dumps(res).casefold()
        for term in forbidden_terms:
            assert term not in json_str, f"Forbidden term '{term}' found in patient resource"

