"""
update_golden_masters.py

Post-checkpoint corrections to golden master files per human review feedback.

Changes applied:
1. BSchacter: recap_tax_op remains null (parser limitation confirmed, no per-section tax/OP in PDF);
   case_metadata already populated from parser. No changes needed.

2. Customer Copy:
   - case_metadata: populate claim_number, policy_number, property_address, date_of_loss,
     date_inspected, price_list, loss_type from PDF (page 3)
   - Stairs section: add 5 line items extracted from PDF (items 27-31, total $1,602.34)

3. Lachman StateFarm:
   - case_metadata: populate from PDF page 3 (claim_number, policy_number, property_address,
     date_of_loss, date_inspected, price_list, loss_type)
   - PRC RESTORATION INC.: fix line item — item 323 "Cleaning (Bid Item)" has total 14,137.76
     (no tax, no OP). Current golden has incorrect tax=14137.76; fix to tax=0.0.

4. Kalyvas StateFarm:
   - case_metadata: populate from PDF page 3 (claim_number, policy_number, property_address,
     date_of_loss, date_inspected, price_list, loss_type, deductible)
"""

import json
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), '..', '..')
GOLDEN_DIR = os.path.join(BASE, 'parser', 'tests', 'golden', 'final-drafts')


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'Saved: {path}')


def update_customer_copy():
    path = os.path.join(GOLDEN_DIR, 'statefarm', 'customer_copy.golden.json')
    d = load_json(path)

    # 1. Populate case_metadata from PDF page 3 (confirmed via pdfplumber extraction):
    # Insured: SCHACTER, BARBARA
    # Estimate: 75-79D9-35K
    # Property: 935 CHATTANOOGA AVE, PACIFIC PLSDS, CA 90272-2328
    # Claim Number: 7579D935K (display format: 75-79D9-35K)
    # Policy Number: 71GFE6010 (display format: 71-GF-E601-0)
    # Price List: CALA28_AUG25
    # Type of Loss: Fire
    # Date of Loss: 1/7/2025
    # Date Inspected: 3/22/2025
    d['case_metadata']['claim_number'] = '75-79D9-35K'
    d['case_metadata']['policy_number'] = '71-GF-E601-0'
    d['case_metadata']['property_address'] = '935 CHATTANOOGA AVE, PACIFIC PLSDS, CA 90272-2328'
    d['case_metadata']['date_of_loss'] = '2025-01-07'
    d['case_metadata']['date_inspected'] = '2025-03-22'
    d['case_metadata']['price_list'] = 'CALA28_AUG25'
    d['case_metadata']['loss_type'] = 'Fire'

    # 2. Add Stairs section line items (extracted from PDF page 13, items 27-31)
    # PDF shows these 5 items under Stairs section, total = $1,602.34
    stairs_line_items = [
        {
            'item_number': 27,
            'description': "I-joist - 9 1/2\" deep - 1 3/4\" flange",
            'qty': 74.0,
            'unit': 'LF',
            'unit_price': 5.83,
            'tax': 17.79,
            'op': 89.84,
            'total': 539.05
        },
        {
            'item_number': 28,
            'description': 'Sheathing - OSB - 3/4\" - tongue and groove',
            'qty': 64.0,
            'unit': 'SF',
            'unit_price': 3.26,
            'tax': 7.78,
            'op': 43.28,
            'total': 259.70
        },
        {
            'item_number': 29,
            'description': 'Drilled bottom plate - 2\" x 6\" treated lumber',
            'qty': 30.0,
            'unit': 'LF',
            'unit_price': 5.11,
            'tax': 4.56,
            'op': 31.58,
            'total': 189.44
        },
        {
            'item_number': 30,
            'description': 'Seal & paint stair tread - per side - per LF',
            'qty': 34.08,
            'unit': 'LF',
            'unit_price': 8.89,
            'tax': 3.82,
            'op': 61.36,
            'total': 368.15
        },
        {
            'item_number': 31,
            'description': 'Seal & paint stair riser - per side - per LF',
            'qty': 34.08,
            'unit': 'LF',
            'unit_price': 5.94,
            'tax': 2.56,
            'op': 41.00,
            'total': 246.00
        }
    ]

    for section in d['sections']:
        if section['section_name'] == 'Stairs':
            section['line_items'] = stairs_line_items
            # Update computed_total and validation_delta to reflect newly extracted items
            # PDF shows: Totals: Stairs  36.51  267.06  1,602.34
            section['section_totals']['computed_total'] = '1,602.34'
            section['section_totals']['validation_delta'] = '0.00'
            print('  Updated Stairs section: added 5 line items, computed_total=1,602.34')
            break

    save_json(path, d)

    # Report
    secs = d.get('sections', [])
    total_items = sum(len(s.get('line_items', [])) for s in secs)
    print(f'  customer_copy.golden.json: {len(secs)} sections, {total_items} total line items')


def update_lachman():
    path = os.path.join(GOLDEN_DIR, 'statefarm', 'lachman_sf.golden.json')
    d = load_json(path)

    # 1. Populate case_metadata from PDF page 3:
    # Insured: CHEN, KENNETH
    # Estimate: 75-79J8-65X
    # Property: 1115 LACHMAN LN, PACIFIC PLSDS, CA 90272-2227
    # Claim Number: 7579J865X (display format: 75-79J8-65X)
    # Policy Number: 75C9A1815
    # Price List: CALA28_JAN25
    # Type of Loss: Smoke
    # Deductible: $0.00
    # Date of Loss: 1/8/2025
    # Date Inspected: 2/18/2025
    d['case_metadata']['claim_number'] = '75-79J8-65X'
    d['case_metadata']['policy_number'] = '75C9A1815'
    d['case_metadata']['property_address'] = '1115 LACHMAN LN, PACIFIC PLSDS, CA 90272-2227'
    d['case_metadata']['date_of_loss'] = '2025-01-08'
    d['case_metadata']['date_inspected'] = '2025-02-18'
    d['case_metadata']['price_list'] = 'CALA28_JAN25'
    d['case_metadata']['loss_type'] = 'Smoke'

    # 2. Fix PRC RESTORATION INC. line item:
    # PDF shows: 323. Cleaning (Bid Item) 1.00EA 14,137.76*EN 0.00 14,137.76
    # tax=0.00, no OP column in this doc (lachman has TAX then RCV, no GCO&P)
    # Current golden has tax=14137.76 which is wrong (that's the total echoed into tax field)
    for section in d['sections']:
        if section['section_name'] == 'PRC RESTORATION INC.':
            section['line_items'] = [
                {
                    'item_number': 323,
                    'description': 'Cleaning (Bid Item)',
                    'qty': 1.0,
                    'unit': 'EA',
                    'unit_price': 14137.76,
                    'tax': 0.0,
                    'op': 0.0,
                    'total': 14137.76,
                    '_note': 'Bid item (EN flag). No tax or O&P applied.'
                }
            ]
            print('  Fixed PRC RESTORATION INC.: corrected tax from 14137.76 to 0.0')
            break

    save_json(path, d)

    secs = d.get('sections', [])
    total_items = sum(len(s.get('line_items', [])) for s in secs)
    print(f'  lachman_sf.golden.json: {len(secs)} sections, {total_items} total line items')


def update_kalyvas():
    path = os.path.join(GOLDEN_DIR, 'statefarm', 'kalyvas_sf.golden.json')
    d = load_json(path)

    # Populate case_metadata from PDF page 3:
    # Insured: KALYVAS, JAMES
    # Estimate: 75-79F9-18M3
    # Property: 16640 Via Pacifica, Pacific Plsds, CA 90272-1947
    # Claim Number: 7579F918M (display format: 75-79F9-18M3)
    # Policy Number: 71J8B0543
    # Price List: CALA28_JAN25
    # Type of Loss: Smoke
    # Deductible: $10,925.00
    # Date of Loss: 1/7/2025
    # Date Inspected: 7/15/2025
    d['case_metadata']['claim_number'] = '75-79F9-18M3'
    d['case_metadata']['policy_number'] = '71J8B0543'
    d['case_metadata']['property_address'] = '16640 Via Pacifica, Pacific Plsds, CA 90272-1947'
    d['case_metadata']['date_of_loss'] = '2025-01-07'
    d['case_metadata']['date_inspected'] = '2025-07-15'
    d['case_metadata']['price_list'] = 'CALA28_JAN25'
    d['case_metadata']['loss_type'] = 'Smoke'

    save_json(path, d)

    secs = d.get('sections', [])
    total_items = sum(len(s.get('line_items', [])) for s in secs)
    print(f'  kalyvas_sf.golden.json: {len(secs)} sections, {total_items} total line items')


def verify_bschacter():
    """BSchacter: no changes needed. recap_tax_op=null is confirmed (parser limitation).
    case_metadata already populated from parser output. Report current state."""
    path = os.path.join(GOLDEN_DIR, 'bschacter.golden.json')
    d = load_json(path)
    secs = d.get('sections', [])
    total_items = sum(len(s.get('line_items', [])) for s in secs)
    r = d.get('recaps_and_summaries', {})
    print(f'  bschacter.golden.json: {len(secs)} sections, {total_items} total line items')
    print(f'  recaps: { {k: bool(v) for k, v in r.items()} }')
    print(f'  recap_tax_op: null (parser limitation - BSchacter uses category recap, not per-section tax/OP table)')


def main():
    print('=== Updating golden master files ===')
    print()

    print('1. BSchacter (verify, no changes needed):')
    verify_bschacter()
    print()

    print('2. Customer Copy StateFarm:')
    update_customer_copy()
    print()

    print('3. Lachman StateFarm:')
    update_lachman()
    print()

    print('4. Kalyvas StateFarm:')
    update_kalyvas()
    print()

    print('=== Done ===')


if __name__ == '__main__':
    main()
