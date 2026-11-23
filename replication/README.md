# Supplementary Material S1

**Value-level provenance for carbon inventory data under source revisions**
Luiz Santos, Regina Braga, José Maria N. David, Victor Ströele (Federal University of Juiz de Fora)

This package contains the ledger, the two pipelines, the source extracts and the scripts that produce every number reported in Sections 4 and 6 of the paper.

## Contents

```
code/      ledger, pipelines and experiments (Python)
gee/       Google Earth Engine script that extracts the soil carbon means (P1)
data/      source extracts used by the pipelines
results/   outputs of the scripts, as reported in the paper
```

### code/

| File | Role |
|---|---|
| `engine.py` | the ledger: values, contracts (`Meta`), derivations, statuses, impact analysis, rewiring |
| `stores.py` | exports to PROV-O (rdflib) and to relational lineage tables (SQLite); impact queries in SPARQL and SQL |
| `shapes.py` | SHACL shapes S1–S3 |
| `attribution.py` | attribution of the change of a derived value to its source values, along the derivation links |
| `evaluate.py` | E1 protocol: incremental update against a full rebuild |
| `p1_carbofarm.py` | pipeline P1, CarboFarm farm-area integration; source versions V0–V2 |
| `p2_national.py` | pipeline P2, Tier 1 livestock estimate linked to PRIMAP-hist; transcribed IPCC 2006 and 2019 factor tables, GWP AR5/AR6, regional mapping |
| `p3_brasil.py` | pipeline P3, soil carbon stocks of all 5,569 Brazilian municipalities, 2017-2021, three MapBiomas version pairs |

### Which script produces which result

| Script | Paper | Output |
|---|---|---|
| `run_p1.py` | Table 2, P1 rows; Section 6.1 | `results/e1_p1.json` |
| `run_p2.py` | Table 2, P2 rows; Section 6.1 | `results/e1_p2.json` |
| `run_p2_extra.py` | Section 6.1, 32.3% of 2020 enteric CH₄ without a factor | `results/e1_p2_extra.txt` |
| `e2_scale.py` | Section 6.5, scale | `results/e2_scale.json` |
| `e3_mutations.py` | Table 3, injected defects | `results/e3_mutations.json` |
| `e4_real_defects.py` | Section 6.3, problems in the CarboFarm release | `results/e4_real_defects.json` |
| `e5_questions.py` | Table 4, verification questions | `results/e5_questions.json` |
| `run_stores.py` | Section 6.5, SQL and SPARQL against the in-memory analysis | `results/stores_equivalence.json` |
| `run_shapes.py` | Section 6.5, SHACL against the ledger (450 farm areas) | `results/shacl_equivalence.json` |
| `run_p3.py` | Table 2, P3 rows; Section 6.1 and Figure 3; Section 6.5 | `results/e1_p3.json` |
| `e6_practice.py` | Section 6.6 and Table 5, OpenLineage and Great Expectations | `results/e6_practice.json` |
| `e7_explain.py` | Section 6.7 and Figure 4, attribution of the two MapBiomas revisions of P3 | `results/e7_explain.json` |
| `e7_openlineage.py` | Section 6.7, the same questions on the OpenLineage graph of P3 | `results/e7_openlineage.json` |

Run each script from inside `code/`, for example `cd code && python run_p1.py`. Timings will differ from the paper; counts will not.

## Requirements

Python 3.11 or later with pandas, numpy, openpyxl, xlrd, rdflib, pyshacl and country_converter:

```
pip install pandas numpy openpyxl xlrd rdflib pyshacl country_converter
```

`e6_practice.py` and `e7_openlineage.py` also need `great_expectations` (1.24) and `openlineage-python` (1.54).

The paper's runs used Python 3.13, pandas 3.0, rdflib 7.6, pyshacl 0.40 and country_converter 1.3.

## Data

| File | Source | Licence |
|---|---|---|
| `data/gee_solo_2021_versoes.csv` | MapBiomas soil carbon (beta 2.1 and collection 3) by municipality and land-cover class (collections 7.1 and 10), 2021, extracted with `gee/carbofarm_solo_versoes.js` | MapBiomas data, CC BY 4.0 |
| `data/mapbiomas_brasil/brasil_solo_*.csv` | the same extraction for all Brazilian municipalities, 2017-2021, three version pairs, from `gee/brasil_solo_versoes.js` (municipal boundaries: geoBoundaries ADM2) | MapBiomas data, CC BY 4.0 |
| `data/contextos_versoes.csv` | municipality-and-class contexts in each version | derived from the above |
| `data/carbofarm/data_integration_all_areas_final.csv` | CarboFarm public release (Santos, 2024) | authors' own release |
| `data/crop_emission_rate.xls` | CarboFarm intermediate table of emission rates (BRLUC by municipality and crop) | authors' own release |
| `data/primap/` | PRIMAP-hist v2.6 and v2.7, final, with the publisher's change list (Gütschow et al., 2024, 2025), Zenodo | CC BY 4.0 |
| `data/faostat/emn_cache*.csv` | extracts of FAOSTAT Livestock Manure (domain EMN): head counts and nitrogen left on pasture, 2015–2022 and the longer ranges used in E2 | FAOSTAT, CC BY 4.0 |

The full FAOSTAT file is not included. The scripts read the extracts in `data/faostat/`. To rebuild the extracts, download the bulk file `Environment_LivestockManure_E_All_Data_(Normalized).csv` from FAOSTAT (domain EMN), place it in `data/faostat/`, and delete the `emn_cache*.csv` files.

The IPCC emission factors (2006 Guidelines and 2019 Refinement, Volume 4, Tables 10.10, 10.11 and 11.1) are transcribed in `code/p2_national.py`. The IPCC documents themselves are not redistributed.

## Earth Engine extraction

`gee/brasil_solo_versoes.js` does the same for every municipality and the years 2017-2021, exporting one CSV per version pair. `gee/carbofarm_solo_versoes.js` runs in the Earth Engine Code Editor. It reads the public MapBiomas assets under `projects/mapbiomas-public/assets/brazil/`, computes the mean 0–30 cm soil organic carbon stock (t C/ha) of each land-cover class in the six CarboFarm municipalities for 2021, and exports one CSV to Google Drive. The comments in the script are in Portuguese.

## Licence

Code: MIT. Data: see the table above.
