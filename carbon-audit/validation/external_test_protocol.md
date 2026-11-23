# Protocol for transfer tests

The protocol was written before execution of the transfer tests. This is a development validation protocol, not a preregistration or a blinded external evaluation.

## Data

Use NOAA GML monthly CO2 mole fractions at Mauna Loa and for the global marine surface. Use World Bank WDI forest area and land area for twelve countries. These series were not used to implement the declaration interface. The World Bank indicators originate from FAO land statistics, distinct from the livestock indicators used in P2. Their provenance is not independent of FAO as an institution.

Use 2015 to 2023 for the initial plans. Reserve 2024 for a NOAA extension and New Zealand for a WDI context addition where available. Record source URLs, download timestamps, metadata and SHA256 hashes. Do not describe changes to test copies as published source revisions.

## Computations

NOAA: station minus global concentration by month, equal weight means of the twelve monthly values by year, and the difference between those means. These means describe the selected monthly records and do not replace annual estimates published by NOAA. Do not interpret a concentration as an emissions inventory.

WDI: forest area divided by land area for each country and year, sums of forest and land areas over the selected countries, and their ratio. Do not label the selected country aggregate as a global estimate.

## Acceptance criteria

1. Adapt source files through a separate adapter and JSON declarations, without modifying the audit engine.
2. Check all baseline outputs through Decimal or SQLite arithmetic that does not call ledger operations.
3. Apply controlled numeric changes, source key withdrawal, unit mismatch, zero denominator, duplicate keys and context addition to test copies. Compare predicted states and changed output sets with the engine output.
4. Check rejection of an unsupported operation and document that limitation.
5. Execute a source plan through the HTTP API and inspect its results through the dashboard. Verify file import in the hosted interface where available.
6. Freeze engine and interface hashes before execution. Record every code change, failure and repair. Passing an adapter test does not establish support for arbitrary source formats or computations.

## Interpretation

Report transfer cases, failures, adapter requirements and scope. Do not infer usability benefits without a participant study. Do not claim that the dashboard is the scientific contribution. Its role is to expose the provenance record produced by the method.
