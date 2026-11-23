# Reproduction of article figures

Figure 4 uses the 2020 state stock comparison between V0 and V1. Figure 5 uses the eight classes with the largest absolute stock changes in 2021 between V1 and V2. The dashboard also exposes the complete class list and years 2017 to 2021. NOAA records cover 2015 to 2023.

From the carbon-audit directory, run `python src/reproduce_charts.py` to derive chart records from the frozen CSV extracts. This step checks national differences against E7. Run `node src/export_figures.mjs` to generate SVG, CSV and JSON files for figures 4 and 5. This command executes the same plotting function used by the dashboard and checks the eight published class changes against E7. Keep carbon-audit and carbon-provenance-lab as sibling directories.

The SVG exported by the published dashboard was compared byte for byte with the SVG used for article figure 5. They matched. PDF and PNG copies in the revision folder were rendered from the SVG exports. In the dashboard, Print or save PDF uses the browser print dialog.

Available means that a plotting record has a value. It is not the engine contract status ok. Source withdrawals and contract violations retain their engine statuses in Value inspection. The chart module does not infer semantics for imported datasets. The four source cases use explicit adapters and archive records.

The NOAA figure shows source concentration records, not a published source revision history. The controlled withdrawal case remains available through Inspect source records.
