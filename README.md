# Effects of source revisions on carbon inventory calculations

Replication package matched to Artigo_C_CAS_adequado_20261120.docx.
The manuscript is not included in this repository.
verification/verification_report.json identifies it by SHA256 and maps its results to the rerun checks.

## Layout

carbon-audit/replication contains the original S1 code and E1 to E7 records. Restore its source extracts from the data release asset before execution.
carbon-audit/src contains the declaration interface and scripts for E8 and E9.
carbon-audit/comparison contains E10 to E16, protocols, source manifests and results.
carbon-provenance-lab/dist contains the dashboard and the plotting function.
research_outputs/exports contains article figures 4 and 5 with CSV, JSON and SVG exports.
verification contains the checks from 23 November 2026 and rerun records.
Keep carbon-audit and carbon-provenance-lab as sibling directories.

## Restore the source data before running analyses

The replication source extracts are distributed as a release asset because five CSV files exceed the browser upload limit. Download Article_C_data_20261123.zip from this repository's GitHub Releases page. Keep the ZIP outside the repository folder.

From the repository root, run:

```text
python restore_data.py --archive /path/to/Article_C_data_20261123.zip
```

On Windows, for example:

```text
python restore_data.py --archive "C:\Users\YOUR_NAME\Downloads\Article_C_data_20261123.zip"
```

Alternatively, pass the HTTPS release asset URL with --url. The script verifies the archive checksum, restores the original paths and verifies every extracted data file. Existing files with a different checksum are refused.

The data file contents are unchanged. data_release_manifest.json records their sizes and SHA256 hashes. Run the analysis commands below only after restoration.

## Upload this package to GitHub

1. Extract Article_C_GitHub_repository_20261123.zip and upload its contents to the repository. Do not upload the ZIP as a source file.
2. Create a GitHub release, for example v1.0.0.
3. Attach Article_C_data_20261123.zip to that release as a binary asset. Do not extract it into the repository before the source upload.
4. State in the release description that the data archive belongs to this code version. Users can then restore it with restore_data.py.
5. If the browser reports a limit on the number of files in one upload, upload the folders in separate batches.

The repository and the data asset exclude the manuscript.

## Installation

Use Python 3.11 or later and Node 20 or later.
The checks in verification used the available Python 3.12 environment. They do not represent a fresh installation from requirements.txt.
From the repository root, install the dependencies:

```text
python -m pip install -r requirements.txt
```

Earth Engine is optional for cached reconciliation. A new map retrieval also needs carbon-audit/requirements-earthengine.txt, your own account and an enabled project.
No Google credentials are included.
The development build of ProvSQL and its matched runtime are retained with their licenses under comparison/vendor.

## Reproduce the analyses

Change directory to carbon-audit. Run these commands in order:

```text
python -m unittest discover -s tests -v
python src/prospective.py
python src/external_transfer.py
python comparison/run_python_sql.py
node comparison/run_provsql.mjs
node comparison/native_features.mjs
python comparison/total_class_differences.py
python comparison/harmonize_legends.py
python comparison/unmapped_sensitivity.py
python comparison/stability_analysis.py
python comparison/reconcile_pixels.py
python comparison/reporting_consequence.py
python comparison/attribution_sensitivity.py
python src/reproduce_charts.py
node src/export_figures.mjs
```

These commands write rerun outputs. Preserve a copy of the release if the archived outputs are needed for byte comparisons.
The original E1 to E7 execution commands and dependencies remain in carbon-audit/replication/README.md. That README documents the original release and uses its original figure numbering. The article figures 4 and 5 are mapped in carbon-audit/CHARTS.md.

## Dashboard

From carbon-audit, run python src/server.py and open http://127.0.0.1:8765.
On Windows, start-dashboard.cmd selects a local virtual environment or an installed Python.
The dashboard presents the method outputs. Analyses and figure export do not require the interface.

## Checks for this release

The 13 engine tests passed. Reruns of E8 to E16 and the figure exports reproduced the results checked against the manuscript. E14 was reconciled from the 48 cached map queries, without new map retrieval.
Tables 7 to 12 and the abstract results have assertions in verification/verification_report.json.
The original E1 to E7 full runs were not repeated in this audit. Their scripts, inputs and archived outputs remain supplied.
The two path fixes change file resolution only. The engine files and scientific protocols were preserved.
The dashboard launcher no longer depends on Codex.

## Publication and citation

The article cites the original S1 Zenodo record and describes the extension as a supplement. This release has not been uploaded to that deposit by this task.
After you publish the repository and archive its release, add that repository address and release DOI to the article availability statement.
The source extracts listed in data_release_manifest.json are distributed in a separate GitHub release asset. They are excluded from version control and restored before analysis. The manuscript is not distributed in the repository or data asset.
Existing licenses and source notices are retained. The original S1 software license is carbon-audit/replication/LICENSE. ProvSQL and other vendored components retain their own notices.

## Language and source identifiers

Documentation, interface labels, test descriptions and source acquisition instructions are in English. Internal editorial notes are not part of this submission package. Original source headers, asset identifiers, place names, source publications and bibliographic titles retain their spelling. They are source identifiers rather than interface prose. The data dictionary below explains the retained source fields.

| Source field | Meaning |
| --- | --- |
| municipio | Municipality name |
| ano | Year |
| classe | Land cover class code |
| versao_solo | Soil source version |
| versao_cobertura | Land cover source version |
| media_t_C_ha | Mean carbon stock in tonnes of carbon per hectare |
| area_ha | Area in hectares |
| uf | Brazilian state |

Scientific input files, numeric outputs and frozen protocols are unchanged. Translation changes are listed in verification/language_review.json.
