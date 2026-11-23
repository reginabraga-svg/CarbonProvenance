# E10 to E16 reproduction

The tests compare declared audit rules and source revision effects. They do not establish a new provenance algebra, exclusive system capability or audit performance with participants.

## E10

Run `python run_python_sql.py` from this directory. The script reads the frozen `protocol.json`, verifies its hash and executes AuditLedger and the independent SQL reconstruction in SQLite. It writes the SQL declarations for PostgreSQL. Run `node run_provsql.mjs` to execute the matched WebAssembly ProvSQL distribution in vendor/runtime. Node 20 or later is required. The tested Node version is recorded in environment.json. No Docker, WSL or PostgreSQL service is required.

The complete approaches agree with 574 expected final output records. The declaration adapter rejects one unsupported operation case separately. That refusal is not a ProvSQL feature limitation. The 17 remaining cases execute in ProvSQL. SQL without contracts has ten disagreements and SQL without history has five.

ProvSQL executes source modifications, SQL arithmetic and query provenance. Plain SQL views over its actual source snapshot implement the domain contracts and historical state labels. Those policy views use the same independent SQL as the SQLite reference. This is one policy implementation ported between runtimes, not three independently authored status classifiers. Native arithmetic is checked against the policy value for every computable output. Raw arithmetic and provenance tokens remain in provsql_results.json, including cases where the application policy rejects a number.

The facts table has no physical primary key on the business key. The source adapter checks input key uniqueness, and the harness requires one actual row per output. The tested update provenance preserves prior rows and conflicted with the first primary-key design. schema_adaptation.txt and provsql_initial_pk_results.json retain that configuration attempt. A nested outer-join version of the queries was interrupted during the NOAA case. The final runner separates policy views from native arithmetic joins and fixes join expansion limits. It is not interpreted as a system performance comparison. No timing ranking is reported.

protocol_before_fixture_fix.json and fixture_erratum.txt record an input aliasing correction. The expected states were not changed to match the implementations. These controls were specified with AI assistance. No independent human adjudication has been performed.

Run `node native_features.mjs` for a separate native capability check. It loads its initial facts before annotation, checks where provenance for that initial query, then enables modification tracking and checks UPDATE, DELETE, token retention and undo. An earlier trial annotated before INSERT with modification tracking enabled and where_provenance could not resolve an input gate. This configuration observation is not generalized to stable native ProvSQL releases. The capability check does not establish where-provenance recovery for every update-generated token.

The vendored matched PGlite and ProvSQL assets were retrieved from https://provsql.org/playground/ on 16 November 2026. Their download manifest contains SHA256 hashes. The tested extension identifies itself as 1.14.0-dev. It is a development build, not a stable native server release. The upstream smoke test passed before comparison. Licenses and the upstream test are retained in vendor.

## E11

Run `python total_class_differences.py` to reconstruct stocks from the frozen MapBiomas extracts and apply E11_protocol.json. This is a retrospective descriptive extension after E1 to E10 were known. Its protocol preceded calculation of its threshold results. The first run stopped at a denominator assertion. The zero-baseline rule and the five exclusions are recorded in E11_denominator_note.txt. No threshold was selected after observing the results.

There are 27,845 municipality-year records and 27,840 with a positive baseline. The five excluded records have zero stock in both versions. At thresholds of 0.1, 1, 5 and 10 percent, the counts of class alerts without total alerts are 27,840, 27,685, 24,167 and 17,816. No total alert occurs at those thresholds. Gross class difference is the sum of absolute class changes divided by the previous total. It counts changes of both signs. It is not carbon transport, a measurement of error or an environmental trend. The municipality-year records are not independent samples.

## Remaining research

There is no comparison with another attribution software implementation, participant study, GProM execution, national scale ProvSQL benchmark or rerun of GX/OpenLineage with additional domain rules. The outputs do not establish novelty or publication readiness on their own. The manuscript narrows the contribution to an audit procedure and the documented source revision effects.


## E12

Run `python harmonize_legends.py` to reproduce the common hierarchy aggregation test. E12_protocol.json declares the code correspondences and E12_sources retains the official PDFs and hashes. The original-code alert counts reproduce E11. Stock totals and net differences are preserved by both declared aggregations. Independent CSV parsing and math.fsum reconcile 1,330,447 groups. The test is not a pixel crosswalk or a complete validation of class definition equivalence.

Run `python unmapped_sensitivity.py` for the labelled followup check of code 0. It was defined after the primary E12 result. It keeps the denominator and records and removes only the absolute code 0 difference from the gross numerator. The 1 percent level 1 alert count is 25,805 instead of 25,828.

The residual indicates source version differences at these groupings. It does not determine source errors, environmental trends or the causes of the mapping differences. E14 now supplies pixel group transitions for selected cases. No audit participant experiment is included.


E13 stability followup

Run python comparison/stability_analysis.py from carbon-audit. It reads the fixed E12 level1 CSV and checks its input and protocol hashes. This retrospective sensitivity adds no source release or pixel validation. See E13_protocol.json, E13_results.json and E13_*.csv.


## E14

Use the full Pacote_arquitetura_dashboard.zip for source extracts and the article. The comparison only ZIP does not contain the replication source directory. Work from carbon-audit. Install requirements-earthengine.txt in your Python environment for new map retrieval. Authenticate with your own Earth Engine account and use your own enabled project. Run:

```text
python comparison/pixel_comparison.py --project PROJECT --prepare-only
python comparison/pixel_comparison.py --project PROJECT
python comparison/reconcile_pixels.py
```

The optional --credential-file argument points to credentials outside the package. No credentials are supplied. New map retrieval requires network access. Cached E14_map_summaries and the exact E14_assets.json allow reconciliation without Google access. Existing cache files are reused. Preserve them before a deliberate new retrieval. The case list is purposive and was selected after E13. The native grid origins differ by whole pixels, so they share a lattice. E14 does not test sensitivity to a fractional pixel shift or assess map accuracy.

## E15 and E16

Install requirements-analysis.txt from carbon-audit and run:

```text
python comparison/reporting_consequence.py
python comparison/attribution_sensitivity.py
```

These scripts use the archived replication source extracts. They do not need the dashboard or Earth Engine. E15 reports class stocks and shares. E16 tests three allocation conventions for source revision effects. Protocols, hashes, CSV output and independent arithmetic checks accompany each experiment. The reporting thresholds are descriptive. Attribution is an accounting allocation and does not identify physical causes.

release_manifest.json records hashes of the comparison files. The manuscript is excluded from this repository. See the root README and verification report for the current package audit. The new extension files have not been uploaded to the original Zenodo deposit.
