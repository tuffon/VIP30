# Coverage Gap Report — Phase 25

Generated: 2026-03-08

This report is the v2.5 parser-fix input. Rough-draft documents are the
regression baseline; final-draft gaps are the v2.5 fix targets.

## Summary

| Document | Doc Type | Sections (parser/golden) | Coverage | Metadata |
|----------|----------|--------------------------|----------|----------|
| lachman | rough-draft | 32/32 | 100% (32/32) | 3 gaps |
| kalyvas | rough-draft | 40/40 | 100% (40/40) | 3 gaps |
| bschacter | contractor-final | 0/29 | 0% (0/29) | 3 gaps |
| sf_bschacter | statefarm | 31/31 | 3% (1/30) | 4 gaps |
| lachman_sf | statefarm | 34/34 | 97% (33/34) | 4 gaps |
| kalyvas_sf | statefarm | 36/36 | 97% (31/32) | 4 gaps |

## Per-Document Analysis

### rough-drafts/lachman.golden.json

**Doc type:** rough-draft
**Sections:** parser=32  golden=32  coverage=100% (32/32 non-excluded)

**Metadata gaps:**
- `insured_name`: parser=None  golden='Kenneth Chen'
- `price_list`: parser='CALA8X_APR25'  golden='CALA8X_APR25 Restoration/Service/Remodel'
- `property_address`: parser='1115 Lachman Ln Pacific Palisades, CA 90272 Claim Rep.: Nick Cavalluzzi Business: (818) 388-1070'  golden='1115 Lachman Ln, Pacific Palisades, CA 90272'

**All sections matched.** ✓

### rough-drafts/kalyvas.golden.json

**Doc type:** rough-draft
**Sections:** parser=40  golden=40  coverage=100% (40/40 non-excluded)

**Metadata gaps:**
- `insured_name`: parser=None  golden='James Kalyvas'
- `price_list`: parser='CALA8X_MAR25'  golden='CALA8X_MAR25 Restoration/Service/Remodel'
- `property_address`: parser='16640 Via Pacifica Pacific Palisades, CA 90272 Claim Rep.: Jared Boergadine Business: (818) 720-9345'  golden='16640 Via Pacifica, Pacific Palisades, CA 90272'

**All sections matched.** ✓

### final-drafts/bschacter.golden.json

**Doc type:** contractor-final
**Sections:** parser=0  golden=29  coverage=0% (0/29 non-excluded)

**Metadata gaps:**
- `insured_name`: parser=None  golden='Barbara Schacter'
- `price_list`: parser=None  golden='CALA8X_JUL25 Restoration/Service/Remodel'
- `property_address`: parser='935 Chattanooga Ave. Pacific Palisades, CA 90272 Claim Rep.: Jared Boergadine Business: (818) 720-9345'  golden='935 Chattanooga Ave., Pacific Palisades, CA 90272'

**Missing sections (29):**
- Demo/Mitigtation: 1 items, $120,000.00
- General Items: 11 items, $62,013.93
- Insulation: 1 items, $4,872.63
- HVAC: 4 items, $0.00
- Electrical: 14 items, $28,391.81
- Plumbing: 2 items, $868.16
- Appliances: 6 items, $25,439.62
- Window and Patio Doors Replacement: 12 items, $33,744.01
- Main Level: 1 items, $2,217.22
- Entry: 33 items, $7,205.94
- Kitchen: 32 items, $22,704.73
- Living Room: 32 items, $33,198.04
- Fireplace: 2 items, $761.50
- Office: 17 items, $8,593.70
- Office Closet: 19 items, $5,057.30
- Bedroom 1: 25 items, $9,708.36
- Bed1 Closet: 16 items, $2,736.20
- Hall Bathroom 1: 40 items, $14,998.18
- Master bathroom: 30 items, $17,468.48
- Master Bedroom: 37 items, $33,273.30
- Main Hallway: 38 items, $26,248.27
- Laundry Room: 31 items, $9,688.83
- Garage: 33 items, $34,768.57
- Ductwork Cavity: 1 items, $54.55
- Ext_Surfaces: 17 items, $62,508.98
- Hardscapes: 8 items, $12,810.60
- CMU Walls: 8 items, $8,311.45
- Gazebos/Outside Structures: 1 items, $221,160.00
- Labor Minimums Applied: 5 items, $658.05

### final-drafts/statefarm/SF_BSchacter.golden.json

**Doc type:** statefarm
**Sections:** parser=31  golden=31  coverage=3% (1/30 non-excluded)

**Metadata gaps:**
- `claim_number`: parser=None  golden='75-79D9-35K'
- `insured_name`: parser=None  golden='Barbara Schacter'
- `price_list`: parser=None  golden='CALA28_AUG25 Restoration/Service/Remodel'
- `property_address`: parser=None  golden='935 CHATTANOOGA AVE, PACIFIC PLSDS, CA 90272-2328'

**Partial sections (29):**
- Swing Pavillion: items 0/3 (-3)  total $10,070.44/$10,070.44 (+0.00)
- Deck: items 1/12 (-11)  total $12,655.48/$12,655.48 (+0.00)
- Gazebo: items 1/3 (-2)  total $21,255.56/$21,255.56 (+0.00)
- Retaining Wall: items 0/2 (-2)  total $924.57/$924.57 (+0.00)
- Trees, Shrubs and Landscaping: items 0/2 (-2)  total $50,743.85/$50,743.85 (+0.00)
- Debris Removal: items 2/3 (-1)  total $1,304.60/$1,304.60 (+0.00)
- Main Level: items 5/3 (+2)  total $23,087.11/$1,765.29 (+21,321.82)
- Stairs: items 0/5 (-5)  total $1,602.34/$1,602.34 (+0.00)
- Main Level: items 5/19 (-14)  total $23,087.11/$23,087.11 (+0.00)
- Master Bedroom Closet: items 1/7 (-6)  total $453.89/$453.89 (+0.00)
- Bedroom 2 Closet: items 1/7 (-6)  total $479.80/$479.80 (+0.00)
- Bedroom 1 Closet: items 1/7 (-6)  total $410.05/$410.05 (+0.00)
- Hallway Closet: items 1/7 (-6)  total $487.87/$487.87 (+0.00)
- Master Bathroom: items 1/34 (-33)  total $3,084.31/$3,084.31 (+0.00)
- Hallway Bathroom: items 1/25 (-24)  total $1,809.51/$1,809.51 (+0.00)
- Hallway Closet 2: items 1/7 (-6)  total $358.52/$358.52 (+0.00)
- Hallway: items 1/15 (-14)  total $4,534.42/$4,534.42 (+0.00)
- Entrance Closet: items 1/7 (-6)  total $334.88/$334.88 (+0.00)
- Living Room: items 1/12 (-11)  total $3,626.70/$3,626.70 (+0.00)
- Bedroom 1: items 1/12 (-11)  total $1,442.00/$1,442.00 (+0.00)
- Laundry: items 1/12 (-11)  total $1,387.83/$1,387.83 (+0.00)
- Pantry: items 1/7 (-6)  total $298.90/$298.90 (+0.00)
- Master Entrance: items 1/9 (-8)  total $494.37/$494.37 (+0.00)
- Garage: items 1/15 (-14)  total $7,738.88/$7,738.88 (+0.00)
- Entrance: items 1/17 (-16)  total $2,554.35/$2,554.35 (+0.00)
- Master Bedroom: items 1/10 (-9)  total $1,970.94/$1,970.94 (+0.00)
- Bedroom 2: items 1/12 (-11)  total $1,824.64/$1,824.64 (+0.00)
- Kitchen: items 2/23 (-21)  total $7,435.69/$7,435.69 (+0.00)
- General Items: items 0/9 (-9)  total $16,876.12/$16,876.12 (+0.00)

### final-drafts/statefarm/lachman_sf.golden.json

**Doc type:** statefarm
**Sections:** parser=34  golden=34  coverage=97% (33/34 non-excluded)

**Metadata gaps:**
- `claim_number`: parser=None  golden='75-79J8-65X'
- `insured_name`: parser=None  golden='Kenneth Chen'
- `price_list`: parser=None  golden='CALA28_JAN25 Restoration/Service/Remodel'
- `property_address`: parser=None  golden='1115 LACHMAN LN, PACIFIC PLSDS, CA 90272-2227'

**Partial sections (1):**
- PRC RESTORATION INC.: items 0/1 (-1)  total $14,137.76/$14,137.76 (+0.00)

### final-drafts/statefarm/kalyvas_sf.golden.json

**Doc type:** statefarm
**Sections:** parser=36  golden=36  coverage=97% (31/32 non-excluded)

**Metadata gaps:**
- `claim_number`: parser=None  golden='75-79F9-18M3'
- `insured_name`: parser=None  golden='James Kalyvas'
- `price_list`: parser=None  golden='CALA28_JAN25 Restoration/Service/Remodel'
- `property_address`: parser=None  golden='16640 Via Pacifica, Pacific Plsds, CA 90272-1947'

**Partial sections (1):**
- Ext_Surfaces: items 5/7 (-2)  total $140,575.90/$140,575.90 (+0.00)

## Cross-Document Patterns

### Metadata fields null in ALL final-draft documents

- `insured_name`
- `price_list`
- `property_address`

### v2.5 Fix Priority

Ordered by impact (document coverage % gain):

**Final-draft gaps (v2.5 scope):**
- **contractor-final / bschacter**: 0% coverage — 29 missing, 0 partial
- **statefarm / sf_bschacter**: 3% coverage — 0 missing, 29 partial
- **statefarm / kalyvas_sf**: 97% coverage — 0 missing, 1 partial
- **statefarm / lachman_sf**: 97% coverage — 0 missing, 1 partial
