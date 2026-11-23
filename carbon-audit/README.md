# Carbon Provenance Lab

The declaration interface extends the S1 calculation engine. The replication directory retains the S1 code and source extracts. The src directory contains the extension. The dashboard is in the sibling carbon-provenance-lab directory.

## Run the dashboard

From this directory, run python src/server.py and open http://127.0.0.1:8765.
On Windows, start-dashboard.cmd selects an installed Python or a local virtual environment.
Run an evaluation executes a JSON plan through the local server. Export result saves its calculation record.
The hosted site supports inspection and result import. Plan execution requires the local server.
Stop the server with Ctrl+C.

The server accepts plans up to 10 MB and listens on loopback. It checks Host and Origin. Plans supply CSV and declarations. They cannot execute Python code or select server files. This input limit is not a measurement of analysis capacity.

## Architecture

| Component | Implementation | Function |
| --- | --- | --- |
| Source adapter | src/audit.py | Read CSV values and source or row contracts |
| Version registry | Ledger.sources and JSON records | Retain source version and content hash |
| Contract checks | Meta and AuditLedger | Check quantity kind, unit, period and spatial support |
| Dependency graph | AuditLedger | Retain operation inputs and dependency order |
| Impact analysis | apply_update and rewire | Propagate revisions and replace sum inputs |
| HTTP API | src/server.py | Receive plans and return calculation records |
| Dashboard | carbon-provenance-lab/dist | Inspect states, contracts, revisions and dependencies |

## Plan schema

examples/soil_plan.json illustrates the schema. Sources declare name, version, contract and csv. Contracts require qkind, unit, period and support. Nodes declare key, op, inputs and contract. params supplies coefficients and operation expectations.
Supported operations are broadcast, scale, mul, sum, diff, lin and ratio. Plans must form a directed acyclic graph. Source meaning is supplied through declarations.
Revisions declare name and updates. Each update supplies source, version and a full CSV snapshot. Omission of a key withdraws that key. add_nodes adds outputs and rewire replaces sum inputs.

| State | Meaning |
| --- | --- |
| ok | Inputs exist and operation contracts are satisfied |
| contextual | A value is assigned from another spatial support |
| blocked | A contract prevents computation and no number is returned |
| unresolved | An input was never available or the operation has no result |
| orphan | An input was available in an earlier version and was withdrawn |

stale identifies revision impact before recomputation. It is not a final value state. A missing factor is not zero.

## Reproduction

See the root README for installation and the E8 to E16 commands. Original E1 to E7 commands remain in replication/README.md. See CHARTS.md for article figure exports.
The API and behavior tests use Python 3.11 or later and its standard library. P1 and P3 analyses also require pandas and numpy. The S1 experiments have the dependencies listed in replication/README.md and the root requirements.txt.

Run python -m unittest discover -s tests -v for the 13 behavior tests.
Run python src/prospective.py for revision checks without a union of future source contexts. Results are stored in validation/prospective.json.
Run python src/external_transfer.py for the frozen NOAA transfer cases. Results and source hashes are stored in external/transfer_test_report.json. validation/external_test_protocol.md defines the protocol.
New source downloads must retain the earlier snapshot, retrieval date and content hash.

## Scope

Unit aliases come from the S1 engine. There is no QUDT unit conversion. Attribution follows the S1 module and does not cover ratios or products with more than two inputs. The API does not expose all attribution operations. The dashboard presents archived attribution records.
The prospective test covers stocks by class, municipality, state and country. Annual differences and attribution are outside that test. Its counts and execution times have a different scope from E1 and E2.
The NOAA case supplies two concentration series, 216 inputs, 135 baseline outputs and 150 outputs after a year extension. Decimal arithmetic supplies the reference calculations. Controlled changes apply to test copies, not to published NOAA revisions.
World Bank acquisition timed out and is not counted as a completed transfer case. No participant usability result is included.
The root verification report distinguishes the analyses rerun on 23 November 2026 from the archived S1 runs.

## Licenses

The extension follows the S1 MIT license. replication/LICENSE retains that license. Source data and vendored components retain their own licenses and notices.
