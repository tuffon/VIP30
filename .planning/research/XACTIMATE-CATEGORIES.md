# Xactimate Category Codes - Complete Reference

**Researched:** 2026-02-27
**Domain:** Verisk Xactimate / Xactware category taxonomy
**Confidence:** HIGH (official Xactware helpdocs, cross-verified with real parsed estimates)

## Summary

Xactimate uses 3-letter category codes to classify all line items in property insurance estimates. These codes appear in the "Recap by Category" section of Xactimate PDF outputs. The official Xactware documentation lists approximately 90-100 structural/trade category codes plus 30-40 contents-specific sub-category codes (prefixed with content handling designations).

Our current `XACTIMATE_CATEGORY_CODE_MAP` in `core.py` contains 48 code mappings. The official documentation reveals approximately 95 unique structural/trade codes. This means we are missing roughly 47 codes that could appear in parsed estimates.

**Key finding:** The category names in the "Recap by Category" section of Xactimate PDFs use the **full category names** (e.g., "FRAMING & ROUGH CARPENTRY", "HEAT, VENT & AIR CONDITIONING"), NOT the 3-letter codes. The 3-letter codes are internal Xactimate identifiers used for line item prefixes. Our parser correctly extracts the full names, and our `_map_category()` method handles both formats (code-prefixed like "FRM Framing" and full names like "FRAMING & ROUGH CARPENTRY").

**Primary recommendation:** Expand `XACTIMATE_CATEGORY_CODE_MAP` to cover all ~95 codes and add the missing full-name keywords to `CATEGORY_KEYWORDS` to reduce "Other / Unclassified" fallback hits.

## Complete Xactimate Category Code List

### Verified from Official Xactware Documentation (HIGH confidence)

Source: [Category codes in Xactimate online](https://xactware.helpdocs.io/l/enUS/article/gb9lf49tdw-category-codes-in-xactimate-online) and [iOS icons & category codes](https://xactware.helpdocs.io/l/enUS/article/2emr429pte-commercial-residential-category-codes)

#### Structural / Trade Categories

| Code | Full Name (as appears in Recap) | Our Mapped Category | Status |
|------|--------------------------------|---------------------|--------|
| ACC | Accessories - Mobile Home | Miscellaneous / General Requirements | MISSING |
| ACT | Acoustical Treatments | Drywall / Insulation | MISSING |
| APP | Appliances | Appliances / Equipment | MISSING (have APL) |
| ARC | Art Restoration, Conservation | Contents / Packout / Storage | MISSING |
| AWN | Awnings & Patio Covers | Siding / Exterior Finishes | MISSING |
| CAB | Cabinetry | Cabinetry / Millwork | EXISTS |
| CLN | Cleaning | Cleaning / Restoration | EXISTS |
| CNC | Concrete & Asphalt | Masonry / Concrete / Foundation | MISSING |
| CON | Content Manipulation | Contents / Packout / Storage | EXISTS (as COM) |
| CSF | Cleaning (alternate) | Cleaning / Restoration | MISSING |
| DMO | General Demolition | Demolition | MISSING (have as keyword) |
| DOR | Doors | Doors / Windows / Glass | MISSING |
| DRY | Drywall | Drywall / Insulation | EXISTS |
| ELE | Electrical | Electrical | EXISTS |
| ELS | Electrical - Special Systems | Specialty Systems (low voltage, alarms, AV, solar) | MISSING |
| EQA | Misc. Equipment - Agricultural | Appliances / Equipment | MISSING |
| EQC | Misc. Equipment - Commercial | Appliances / Equipment | MISSING |
| EQU | Heavy Equipment | Miscellaneous / General Requirements | MISSING |
| EXC | Excavation | Masonry / Concrete / Foundation | MISSING |
| FCC | Floor Covering - Carpet | Flooring | MISSING |
| FCR | Floor Covering - Resilient | Flooring | MISSING |
| FCS | Floor Covering - Stone | Flooring | MISSING |
| FCT | Floor Covering - Ceramic Tile | Flooring | MISSING |
| FCV | Floor Covering - Vinyl | Flooring | MISSING |
| FCW | Floor Covering - Wood | Flooring | MISSING |
| FEE | Permits and Fees | Permit Fees | MISSING |
| FEN | Fencing | Fencing / Gates | EXISTS |
| FNC | Finish Carpentry / Trimwork | Cabinetry / Millwork | EXISTS (as FIN) |
| FNH | Finish Hardware | Doors / Windows / Glass | MISSING |
| FPL | Fireplaces | HVAC / Mechanical | EXISTS |
| FPS | Fire Protection Systems | Specialty Systems (low voltage, alarms, AV, solar) | MISSING |
| FRM | Framing & Rough Carpentry | Framing / Structural | EXISTS |
| FRP | Fire Proofing | Drywall / Insulation | MISSING |
| GLS | Glass, Glazing, & Storefronts | Doors / Windows / Glass | EXISTS |
| HMR | Hazardous Material Remediation | Cleaning / Restoration | MISSING |
| HVC | Heat, Vent, & Air Conditioning | HVAC / Mechanical | EXISTS |
| INM | Insulation - Mechanical | Drywall / Insulation | MISSING |
| INS | Insulation | Drywall / Insulation | EXISTS |
| LAB | Labor Only | Miscellaneous / General Requirements | MISSING |
| LIT | Light Fixtures | Electrical | EXISTS |
| LND | Landscaping | Landscaping / Trees / Shrubs | MISSING |
| MAS | Masonry | Masonry / Concrete / Foundation | MISSING |
| MBL | Marble - Cultured or Natural | Flooring | MISSING |
| MPR | Moisture Protection | Drywall / Insulation | MISSING |
| MSD | Mirrors & Shower Doors | Doors / Windows / Glass | MISSING |
| MSK | Mobile Homes, Skirting, & Setup | Miscellaneous / General Requirements | MISSING |
| MTL | Metal Structures & Components | Miscellaneous / General Requirements | EXISTS |
| OBS | Obsolete Items | Other / Unclassified | MISSING |
| ORI | Ornamental Iron | Fencing / Gates | MISSING |
| PLA | Interior Lath & Plaster | Drywall / Insulation | MISSING |
| PLM | Plumbing | Plumbing | MISSING (have PLU) |
| PNL | Paneling & Wood Wall Finishes | Cabinetry / Millwork | MISSING |
| PNT | Painting | Painting | EXISTS |
| POL | Swimming Pools & Spas | Pools & Spas | EXISTS |
| PRM | Property Repair & Maintenance | Miscellaneous / General Requirements | MISSING |
| PTG | Painting - Low or No VOC | Painting | MISSING |
| RFG | Roofing | Roofing | EXISTS |
| SCF | Scaffolding | Miscellaneous / General Requirements | MISSING |
| SDG | Siding | Siding / Exterior Finishes | MISSING |
| SFG | Soffit, Fascia, & Gutter | Siding / Exterior Finishes | MISSING |
| SPE | Specialty Items | Specialty Systems (low voltage, alarms, AV, solar) | MISSING |
| SPR | Sprinklers | Specialty Systems (low voltage, alarms, AV, solar) | EXISTS |
| STJ | Steel Joist Components | Framing / Structural | MISSING |
| STL | Steel Components | Framing / Structural | EXISTS |
| STR | Stairs | Framing / Structural | MISSING |
| STU | Stucco & Exterior Plaster | Siding / Exterior Finishes | EXISTS |
| TBA | Toilet & Bath Accessories | Plumbing | MISSING |
| TCR | Trauma/Crime Scene Remediation | Cleaning / Restoration | MISSING |
| TIL | Tile | Flooring | EXISTS |
| TMB | Timber Framing | Framing / Structural | MISSING |
| TMP | Temporary Repairs | Miscellaneous / General Requirements | MISSING |
| USR | User Defined Items | Other / Unclassified | MISSING |
| VTC | Valuation Tool Cost | Other / Unclassified | MISSING |
| WDA | Windows - Aluminum | Doors / Windows / Glass | MISSING |
| WDP | Windows - Sliding Patio Doors | Doors / Windows / Glass | MISSING |
| WDR | Windows Reglazing & Repair | Doors / Windows / Glass | EXISTS |
| WDS | Windows - Skylights | Doors / Windows / Glass | MISSING |
| WDT | Window Treatment | Doors / Windows / Glass | MISSING |
| WDV | Windows - Vinyl | Doors / Windows / Glass | MISSING |
| WDW | Windows - Wood | Doors / Windows / Glass | MISSING |
| WPR | Wallpaper | Painting | MISSING |
| WTR | Water Extraction & Remediation | Cleaning / Restoration | MISSING |
| XST | Exterior Structures | Siding / Exterior Finishes | MISSING |

#### Contents-Specific Categories (appear in contents estimates)

| Code | Full Name (as appears in Recap) | Our Mapped Category |
|------|--------------------------------|---------------------|
| AMA | Contents: Amateur Radio | Contents / Packout / Storage |
| ANT | Contents: Antiques | Contents / Packout / Storage |
| ART | Contents: Artwork | Contents / Packout / Storage |
| BGE | Contents: Board Games/Entertainment | Contents / Packout / Storage |
| BMP | Contents: Books/Maps/Prints | Contents / Packout / Storage |
| CAP | Cont: Clean Appliances | Contents / Packout / Storage |
| CCE | Contents: Coins/Currency/Evidence | Contents / Packout / Storage |
| CDC | Contents: CDs/DVDs/Cassettes | Contents / Packout / Storage |
| CEL | Cont: Clean Electric Items | Contents / Packout / Storage |
| CGN | Cont: Clean - General Items | Contents / Packout / Storage |
| CHF | Cont: Clean - Hard Furniture | Contents / Packout / Storage |
| CLH | Contents: Clothing/Handbags | Contents / Packout / Storage |
| CLM | Cont: Clean Lamps or Vases | Contents / Packout / Storage |
| CMP | Contents: Computer Equipment | Contents / Packout / Storage |
| CPS | Cont: Packing, Handling, Storage | Contents / Packout / Storage |
| CUP | Cont: Clean Upholstery & Soft | Contents / Packout / Storage |
| CWH | Cont: Clean Wall Hangings | Contents / Packout / Storage |
| FRN | Contents: Furniture | Contents / Packout / Storage |
| GUN | Contents: Guns/Firearms | Contents / Packout / Storage |
| HDF | Contents: Home Decor/Furnishings | Contents / Packout / Storage |
| HLT | Contents: Health/Medical | Contents / Packout / Storage |
| HOB | Contents: Hobbies/Crafts | Contents / Packout / Storage |
| HSW | Contents: Housewares | Contents / Packout / Storage |
| INF | Contents: Infant/Children | Contents / Packout / Storage |
| JWL | Contents: Jewelry/Watches | Contents / Packout / Storage |
| KCW | Contents: Kitchenware | Contents / Packout / Storage |
| LGP | Contents: Luggage/Purses | Contents / Packout / Storage |
| LIN | Contents: Linens/Bedding | Contents / Packout / Storage |
| MMM | Contents: Music/Movies/Media | Contents / Packout / Storage |
| MUS | Contents: Musical Instruments | Contents / Packout / Storage |
| OFS | Contents: Office Supplies | Contents / Packout / Storage |
| PCB | Contents: Personal Care/Beauty | Contents / Packout / Storage |
| PER | Contents: Personal Items | Contents / Packout / Storage |
| PET | Contents: Pets/Animals | Contents / Packout / Storage |
| SPG | Contents: Sporting Goods | Contents / Packout / Storage |
| TOL | Contents: Tools | Contents / Packout / Storage |
| TOY | Contents: Toys/Games | Contents / Packout / Storage |

#### Miscellaneous / Administrative Codes

| Code | Full Name | Notes |
|------|-----------|-------|
| BF | Convert to Board Feet | Measurement conversion, not a trade |
| CFB | Cubic Feet Var B | Measurement conversion |
| CAS | Cash | Financial category |
| CRD | Credit | Financial category |
| DOC | Documents | Administrative |
| ELC | Electrical (alternate) | May appear in some versions |
| FEC | Fee Category | Administrative |
| RUP | Round Up | Measurement conversion |

## Current Code Mapping Issues

### Codes in Our Map That Don't Match Official Xactware Codes

| Our Code | Our Mapping | Issue |
|----------|------------|-------|
| ADB | Miscellaneous / General Requirements | Not in official docs; may be version-specific |
| APL | Appliances / Equipment | Official code is APP |
| BAS | Miscellaneous / General Requirements | Not in official docs; may be version-specific |
| CAR | Cabinetry / Millwork | Not in official docs; may be alias for CAB |
| COM | Contents / Packout / Storage | Official code is CON |
| DIA | Miscellaneous / General Requirements | Not in official docs; may be alias for diagnostic |
| ETC | Specialty Systems | Not in official docs |
| FIR | Doors / Windows / Glass | Not in official docs; possibly FPL? |
| GAS | Framing / Structural | Not in official docs |
| GEN | Miscellaneous / General Requirements | Not in official docs |
| MAR | Flooring | Official code is MBL |
| MEC | Framing / Structural | Not in official docs |
| MIT | Miscellaneous / General Requirements | Not in official docs |
| MLD | Cabinetry / Millwork | Not in official docs; may be alias for molding |
| PAI | Painting | Official code is PNT |
| PLU | Plumbing | Official code is PLM |
| POL | Contents / Packout / Storage | Conflicts with official POL = Swimming Pools |
| RST | Miscellaneous / General Requirements | Not in official docs |
| SCA | Miscellaneous / General Requirements | Official code is SCF |
| SEA | Siding / Exterior Finishes | Not in official docs |
| SID | Siding / Exterior Finishes | Official code is SDG |
| SOL | Flooring | Not in official docs; may be an alias |
| TAR | Miscellaneous / General Requirements | Not in official docs |
| TRK | Miscellaneous / General Requirements | Not in official docs |
| TWN | Cabinetry / Millwork | Not in official docs |
| UPH | Contents / Packout / Storage | Not in official docs; may be alias |
| VNT | HVAC / Mechanical | Not in official docs; official is HVC |
| WAT | Cleaning / Restoration | Official code is WTR |
| WEL | Framing / Structural | Not in official docs |
| WOO | Cabinetry / Millwork | Not in official docs |
| WWP | Painting | Official code is WPR |

**Assessment:** Our map contains ~17 codes that match official Xactware codes and ~31 that appear to be non-standard aliases, older version codes, or abbreviations derived from the full category names rather than the official 3-letter codes. These non-standard codes likely come from how our PDF parser extracts text (abbreviations from full names) rather than from the Xactimate internal code system.

### Missing Official Codes (HIGH priority for addition)

These codes appear in official docs and are likely to appear in parsed estimates:

| Code | Full Name | Priority | Rationale |
|------|-----------|----------|-----------|
| CNC | Concrete & Asphalt | HIGH | Common in structural estimates |
| DOR | Doors | HIGH | Very common |
| DMO | General Demolition | HIGH | Very common (currently keyword only) |
| ELS | Electrical - Special Systems | HIGH | Seen in our parsed data as full name |
| FCC | Floor Covering - Carpet | HIGH | Common flooring |
| FCT | Floor Covering - Ceramic Tile | HIGH | Seen in parsed data as full name |
| FCW | Floor Covering - Wood | HIGH | Seen in parsed data as full name |
| FNC | Finish Carpentry / Trimwork | HIGH | Seen in parsed data as full name |
| FNH | Finish Hardware | HIGH | Seen in parsed data as full name |
| FPS | Fire Protection Systems | HIGH | Seen in parsed data |
| HMR | Hazardous Material Remediation | HIGH | Seen in parsed data as full name |
| LAB | Labor Only | HIGH | Seen in parsed data as full name |
| LND | Landscaping | HIGH | Common category |
| MAS | Masonry | HIGH | Common in structural |
| ORI | Ornamental Iron | HIGH | Seen in parsed data |
| PLM | Plumbing | HIGH | Official code (we use PLU) |
| APP | Appliances | HIGH | Official code (we use APL) |
| SDG | Siding | HIGH | Official code (we use SID) |
| SFG | Soffit, Fascia, & Gutter | MEDIUM | Exterior work |
| SPE | Specialty Items | HIGH | Seen in parsed data as full name |
| TBA | Toilet & Bath Accessories | MEDIUM | Plumbing-adjacent |
| TMP | Temporary Repairs | HIGH | Seen in parsed data as full name |
| WDP | Windows - Sliding Patio Doors | HIGH | Seen in parsed data as full name |
| WTR | Water Extraction & Remediation | HIGH | Seen in parsed data as full name |
| XST | Exterior Structures | HIGH | Seen in parsed data as full name |
| CPS | Cont: Packing, Handling, Storage | HIGH | Seen in parsed data as full name |

## Category Names as They Appear in Parsed Estimates

From our actual parsed recap.json files, these are the exact category names that appear in the "Recap by Category" section of real Xactimate PDFs:

### Observed in Our Historical Data

| Recap Name (exact) | Frequency | Our Current Mapping |
|--------------------|-----------|---------------------|
| CLEANING | Common | Cleaning / Restoration (via keyword) |
| CONTENT MANIPULATION | Occasional | Contents / Packout / Storage (via keyword) |
| CONT: PACKING,HANDLNG,STORAGE | Common | Contents / Packout / Storage (via keyword) |
| CONT: CLEAN - GENERAL ITEMS | Occasional | Contents / Packout / Storage (via keyword) |
| GENERAL DEMOLITION | Common | Demolition (via keyword) |
| DOORS | Common | Doors / Windows / Glass (via keyword) |
| ELECTRICAL | Common | Electrical (via keyword) |
| ELECTRICAL - SPECIAL SYSTEMS | Common | Specialty Systems (via keyword) |
| MISC. EQUIPMENT - COMMERCIAL | Occasional | Appliances / Equipment (via keyword) |
| FLOOR COVERING - CERAMIC TILE | Common | Flooring (via keyword) |
| FLOOR COVERING - WOOD | Common | Flooring (via keyword) |
| FENCING | Common | Fencing / Gates (via keyword) |
| FINISH CARPENTRY / TRIMWORK | Common | Cabinetry / Millwork (via keyword) |
| FINISH HARDWARE | Occasional | Doors / Windows / Glass (via keyword) |
| FIREPLACES | Occasional | HVAC / Mechanical (via keyword) |
| FIRE PROTECTION SYSTEMS | Occasional | Specialty Systems (via keyword) |
| HAZARDOUS MATERIAL REMEDIATION | Occasional | Cleaning / Restoration (via keyword) |
| HEAT, VENT & AIR CONDITIONING | Common | HVAC / Mechanical (via keyword) |
| INSULATION | Common | Drywall / Insulation (via keyword) |
| LABOR ONLY | Common | Miscellaneous / General Requirements (via keyword) |
| LIGHT FIXTURES | Common | Electrical (via keyword) |
| LANDSCAPING | Common | Landscaping / Trees / Shrubs (via keyword) |
| MASONRY | Occasional | Masonry / Concrete / Foundation (via keyword) |
| METAL STRUCTURES & COMPONENTS | Occasional | Miscellaneous / General Requirements |
| ORNAMENTAL IRON | Occasional | Fencing / Gates (via keyword) |
| PLUMBING | Common | Plumbing (via keyword) |
| PAINTING | Common | Painting (via keyword) |
| ROOFING | Common | Roofing (via keyword) |
| SPECIALTY ITEMS | Common | Specialty Systems (via keyword) |
| STUCCO & EXTERIOR PLASTER | Common | Siding / Exterior Finishes (via keyword) |
| SWIMMING POOLS & SPAS | Occasional | Pools & Spas (via keyword) |
| TILE | Common | Flooring (via keyword) |
| TEMPORARY REPAIRS | Occasional | Miscellaneous / General Requirements (via keyword) |
| WINDOW TREATMENT | Common | Doors / Windows / Glass (via keyword) |
| WINDOWS - SLIDING PATIO DOORS | Occasional | Doors / Windows / Glass (via keyword) |
| EXTERIOR STRUCTURES | Occasional | Siding / Exterior Finishes (via keyword) |
| WATER EXTRACTION & REMEDIATION | Common | Cleaning / Restoration (via keyword) |
| AWNINGS & PATIO COVERS | Occasional | Siding / Exterior Finishes (via keyword) |
| APPLIANCES | Common | Appliances / Equipment (via keyword) |
| CABINETRY | Common | Cabinetry / Millwork (via keyword) |
| CONCRETE & ASPHALT | Common | Masonry / Concrete / Foundation (via keyword) |
| DRYWALL | Common | Drywall / Insulation (via keyword) |
| HEAVY EQUIPMENT | Occasional | Miscellaneous / General Requirements (via keyword) |
| GLASS, GLAZING, & STOREFRONTS | Occasional | Doors / Windows / Glass (via keyword) |
| FRAMING & ROUGH CARPENTRY | Common | Framing / Structural (via keyword) |

### Recap Group Labels (O&P vs Non-O&P)

Xactimate PDFs group categories under "O&P Items" and "Non-O&P Items" headers in the Recap. The same category name can appear under both groups. Our parser correctly handles this by aggregating totals per category regardless of which group they fall under.

## Recommended Complete Code Map

Below is the recommended expanded `XACTIMATE_CATEGORY_CODE_MAP` that should replace the current one. It includes all official codes plus the non-standard aliases we currently support:

```python
XACTIMATE_CATEGORY_CODE_MAP: Dict[str, str] = {
    # ---- Official Xactware Category Codes ----
    # Cleaning / Restoration
    "CLN": "Cleaning / Restoration",
    "CSF": "Cleaning / Restoration",
    "HMR": "Cleaning / Restoration",
    "TCR": "Cleaning / Restoration",
    "WTR": "Cleaning / Restoration",
    # Contents / Packout / Storage
    "CON": "Contents / Packout / Storage",
    "CPS": "Contents / Packout / Storage",
    "ARC": "Contents / Packout / Storage",
    "CAP": "Contents / Packout / Storage",
    "CEL": "Contents / Packout / Storage",
    "CGN": "Contents / Packout / Storage",
    "CHF": "Contents / Packout / Storage",
    "CLM": "Contents / Packout / Storage",
    "CUP": "Contents / Packout / Storage",
    "CWH": "Contents / Packout / Storage",
    "FRN": "Contents / Packout / Storage",
    # Demolition
    "DMO": "Demolition",
    # Framing / Structural
    "FRM": "Framing / Structural",
    "STJ": "Framing / Structural",
    "STL": "Framing / Structural",
    "STR": "Framing / Structural",
    "TMB": "Framing / Structural",
    # Drywall / Insulation
    "ACT": "Drywall / Insulation",
    "DRY": "Drywall / Insulation",
    "FRP": "Drywall / Insulation",
    "INM": "Drywall / Insulation",
    "INS": "Drywall / Insulation",
    "MPR": "Drywall / Insulation",
    "PLA": "Drywall / Insulation",
    # Painting
    "PNT": "Painting",
    "PTG": "Painting",
    "WPR": "Painting",
    # Flooring
    "FCC": "Flooring",
    "FCR": "Flooring",
    "FCS": "Flooring",
    "FCT": "Flooring",
    "FCV": "Flooring",
    "FCW": "Flooring",
    "MBL": "Flooring",
    "TIL": "Flooring",
    # Doors / Windows / Glass
    "DOR": "Doors / Windows / Glass",
    "FNH": "Doors / Windows / Glass",
    "GLS": "Doors / Windows / Glass",
    "MSD": "Doors / Windows / Glass",
    "WDA": "Doors / Windows / Glass",
    "WDP": "Doors / Windows / Glass",
    "WDR": "Doors / Windows / Glass",
    "WDS": "Doors / Windows / Glass",
    "WDT": "Doors / Windows / Glass",
    "WDV": "Doors / Windows / Glass",
    "WDW": "Doors / Windows / Glass",
    # Cabinetry / Millwork
    "CAB": "Cabinetry / Millwork",
    "FNC": "Cabinetry / Millwork",
    "PNL": "Cabinetry / Millwork",
    # Electrical
    "ELE": "Electrical",
    "ELC": "Electrical",
    "LIT": "Electrical",
    # Plumbing
    "PLM": "Plumbing",
    "TBA": "Plumbing",
    # HVAC / Mechanical
    "FPL": "HVAC / Mechanical",
    "HVC": "HVAC / Mechanical",
    # Roofing
    "RFG": "Roofing",
    # Siding / Exterior Finishes
    "AWN": "Siding / Exterior Finishes",
    "SDG": "Siding / Exterior Finishes",
    "SFG": "Siding / Exterior Finishes",
    "STU": "Siding / Exterior Finishes",
    "XST": "Siding / Exterior Finishes",
    # Masonry / Concrete / Foundation
    "CNC": "Masonry / Concrete / Foundation",
    "EXC": "Masonry / Concrete / Foundation",
    "MAS": "Masonry / Concrete / Foundation",
    # Fencing / Gates
    "FEN": "Fencing / Gates",
    "ORI": "Fencing / Gates",
    # Landscaping / Trees / Shrubs
    "LND": "Landscaping / Trees / Shrubs",
    # Pools & Spas
    "POL": "Pools & Spas",
    # Appliances / Equipment
    "APP": "Appliances / Equipment",
    "EQA": "Appliances / Equipment",
    "EQC": "Appliances / Equipment",
    "EQU": "Appliances / Equipment",
    # Specialty Systems (low voltage, alarms, AV, solar)
    "ELS": "Specialty Systems (low voltage, alarms, AV, solar)",
    "FPS": "Specialty Systems (low voltage, alarms, AV, solar)",
    "SPE": "Specialty Systems (low voltage, alarms, AV, solar)",
    "SPR": "Specialty Systems (low voltage, alarms, AV, solar)",
    # Miscellaneous / General Requirements
    "ACC": "Miscellaneous / General Requirements",
    "LAB": "Miscellaneous / General Requirements",
    "MSK": "Miscellaneous / General Requirements",
    "MTL": "Miscellaneous / General Requirements",
    "PRM": "Miscellaneous / General Requirements",
    "SCF": "Miscellaneous / General Requirements",
    "TMP": "Miscellaneous / General Requirements",
    # Permit Fees
    "FEE": "Permit Fees",
    # Other / Unclassified
    "OBS": "Other / Unclassified",
    "USR": "Other / Unclassified",
    "VTC": "Other / Unclassified",
    # ---- Non-standard aliases (from our existing map, kept for backward compat) ----
    "ADB": "Miscellaneous / General Requirements",
    "APL": "Appliances / Equipment",
    "BAS": "Miscellaneous / General Requirements",
    "CAR": "Cabinetry / Millwork",
    "COM": "Contents / Packout / Storage",
    "DIA": "Miscellaneous / General Requirements",
    "ETC": "Specialty Systems (low voltage, alarms, AV, solar)",
    "FIN": "Cabinetry / Millwork",
    "FIR": "Doors / Windows / Glass",
    "GAS": "Framing / Structural",
    "GEN": "Miscellaneous / General Requirements",
    "MAR": "Flooring",
    "MEC": "Framing / Structural",
    "MIT": "Miscellaneous / General Requirements",
    "MLD": "Cabinetry / Millwork",
    "PAI": "Painting",
    "PLU": "Plumbing",
    "RST": "Miscellaneous / General Requirements",
    "SCA": "Miscellaneous / General Requirements",
    "SEA": "Siding / Exterior Finishes",
    "SID": "Siding / Exterior Finishes",
    "SOL": "Flooring",
    "TAR": "Miscellaneous / General Requirements",
    "TRK": "Miscellaneous / General Requirements",
    "TWN": "Cabinetry / Millwork",
    "UPH": "Contents / Packout / Storage",
    "VNT": "HVAC / Mechanical",
    "WAT": "Cleaning / Restoration",
    "WEL": "Framing / Structural",
    "WOO": "Cabinetry / Millwork",
    "WWP": "Painting",
}
```

## Missing Keyword Patterns

These full-name patterns appear in our parsed data but are NOT currently in `CATEGORY_KEYWORDS`:

| Pattern to Add | Target Category | Source |
|----------------|----------------|--------|
| "METAL STRUCT" | Miscellaneous / General Requirements | Seen in parsed data |
| "WINDOW SLIDING" or "PATIO DOOR" | Doors / Windows / Glass | Seen in parsed data |
| "EXTERIOR STRUCT" | Siding / Exterior Finishes | Seen in parsed data |
| "HEAVY EQUIP" | Miscellaneous / General Requirements | Seen in parsed data |
| "FRAMING" (without ROUGH) | Framing / Structural | Official full name variant |
| "ROUGH CARPENTRY" | Framing / Structural | Official full name variant |
| "FINISH CARPENTRY" | Cabinetry / Millwork | Seen in parsed data |
| "TRIMWORK" | Cabinetry / Millwork | Seen in parsed data |
| "SOFFIT" | Siding / Exterior Finishes | Official category |
| "FASCIA" | Siding / Exterior Finishes | Official category |
| "GUTTER" | Siding / Exterior Finishes | Official category |
| "SKYLIGHT" | Doors / Windows / Glass | Official category |
| "MARBLE" | Flooring | Already exists but verify |
| "LATH" | Drywall / Insulation | Official category |
| "PLASTER" | Drywall / Insulation | Official category (not Stucco) |
| "PANELING" | Cabinetry / Millwork | Official category |
| "SHOWER DOOR" | Doors / Windows / Glass | Official category |
| "MIRROR" | Doors / Windows / Glass | Official category |
| "BATH ACCESSOR" | Plumbing | Official category |
| "TRAUMA" | Cleaning / Restoration | Official category |
| "CRIME SCENE" | Cleaning / Restoration | Official category |
| "EXCAVAT" | Masonry / Concrete / Foundation | Official category |
| "MOISTURE PROTECT" | Drywall / Insulation | Official category |

## How Recap by Category Works in Xactimate

### Structure
1. **Group headers:** "O&P Items" and "Non-O&P Items" (or just "Items" for non-O&P estimates)
2. **Category rows:** Each row shows category name, total, percentage, and coverage breakdown
3. **Subtotals:** "Items Subtotal", "Overhead", "Profit", "Permits and Fees", "Material Sales Tax", "Total"

### Key Observations
- The same category (e.g., "CLEANING") can appear under both O&P and Non-O&P groups
- Category names use FULL NAMES in all caps, not 3-letter codes
- Some categories have compound names: "FLOOR COVERING - CERAMIC TILE", "ELECTRICAL - SPECIAL SYSTEMS"
- Contents categories use prefix: "CONT: PACKING,HANDLNG,STORAGE"
- Our parser already handles both O&P and Non-O&P grouping correctly

## Open Questions

1. **Version differences:** The non-standard codes in our existing map (ADB, BAS, CAR, etc.) may come from older Xactimate versions or regional variants. We should keep them as aliases for backward compatibility but cannot verify their exact origin. **Confidence: LOW**

2. **Commercial vs Residential:** The second Xactware helpdocs page shows additional content-specific codes that appear primarily in contents/personal property estimates. These are well-covered by our "CONT:" keyword prefix matching. **Confidence: MEDIUM**

3. **Code-prefixed vs full-name format:** Our parser sometimes sees "FRM Framing" format (code + name) and sometimes just "FRAMING & ROUGH CARPENTRY" (full name only). The `_map_category()` method handles both paths. No change needed to the matching logic, only the code map and keyword list need expansion. **Confidence: HIGH**

## Sources

### Primary (HIGH confidence)
- [Category codes in Xactimate online - Xactware help](https://xactware.helpdocs.io/l/enUS/article/gb9lf49tdw-category-codes-in-xactimate-online) - Complete list of ~97 codes
- [iOS icons & category codes - Xactware help](https://xactware.helpdocs.io/l/enUS/article/2emr429pte-commercial-residential-category-codes) - Extended list with contents codes (~145 total)
- Real parsed recap.json files from VIP30 project historical data (7 files analyzed)

### Secondary (MEDIUM confidence)
- [Sketch variables in Xactimate online](https://xactware.helpdocs.io/l/enUS/article/q7rfy2iviv-variables-and-category-codes-in-xactimate-online) - Variables page, confirmed codes are separate from measurement vars

### Tertiary (LOW confidence)
- WebSearch results referencing Quizlet flashcards, Brainscape, and TopAdjuster PDFs - used for cross-referencing only

## Metadata

**Confidence breakdown:**
- Official code list: HIGH - sourced from Xactware helpdocs.io (official Verisk documentation portal)
- Full name mappings: HIGH - verified against real parsed estimate data
- Non-standard alias codes: LOW - origin unknown, kept for backward compatibility
- Contents sub-categories: MEDIUM - from official docs but less commonly seen in our estimates
- Missing keyword patterns: HIGH - derived from gap analysis of parsed data vs keyword list

**Research date:** 2026-02-27
**Valid until:** Stable taxonomy; valid for 90+ days. Xactware updates category lists infrequently (yearly at most).
