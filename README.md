# arXiv Submission Day and Citation Counts in Astronomy
 
## Overview
 
Does the day of the week a paper is submitted to arXiv affect its eventual citation count in refereed journals?
 
This repository contains the complete, reproducible analysis pipeline for a bibliometrics study examining whether arXiv announcement day correlates with citations across six major astronomy journals. We analyse 37,173 papers published in 2020–2023 (MNRAS, ApJ, ApJL, ApJS, A&A, JCAP), combining NASA ADS citation data with arXiv submission timestamps.
 
**Key finding:** Papers submitted on weekends receive significantly lower median citations (12–26% deficit) than weekday submissions in five of six journals. Median citations are indistinguishable across Monday–Friday.
 
## Quick Start
 
### Requirements
- Python 3.8+
- Conda (recommended)
- NASA ADS API token (optional — cached data included)
### Installation
 
```bash
# Clone the repository
git clone https://github.com/chirag003214/astroph-weekday-citations.git
cd astroph-weekday-citations
 
# Create and activate the conda environment
conda env create -f environment.yml
conda activate weekday
 
# (Optional) Set your NASA ADS API token
setx ADS_API_TOKEN "your-token-here"  # Windows
export ADS_API_TOKEN="your-token-here"  # macOS/Linux
```
 
### Run the Pipeline
 
```bash
# Analyse a single journal
python run_pipeline.py --journal MNRAS
 
# Or analyse all six journals
for j in MNRAS ApJ A&A ApJL ApJS JCAP; do python run_pipeline.py --journal $j; done
```
 
Results are written to `results/<JOURNAL>/` with tables, figures (PNG + PDF), and a detailed `RESULTS.md` summary.
 
## Directory Structure
 
```
astroph-weekday-citations/
├── README.md                 # This file
├── environment.yml           # Conda environment specification
├── config.py                 # Configuration: ADS queries, file paths
├── run_pipeline.py           # Main entry point
├── make_paper_figures.py     # Generate three publication figures (6-panel)
│
├── src/
│   ├── __init__.py
│   ├── ads_client.py         # NASA ADS API queries and caching
│   ├── arxiv_client.py       # arXiv XML parsing and retry logic
│   ├── schedule.py           # Day-of-week assignment (DST-aware, validated)
│   ├── stats.py              # Median, bootstrap CI, Kruskal–Wallis, Mann–Whitney U
│   └── plots.py              # 10 figures per journal (300 dpi PNG + PDF)
│
├── tests/
│   └── test_schedule.py      # 22 unit tests for day-of-week assignment
│
├── data/
│   └── raw/
│       ├── MNRAS_ads_raw.json        # Cached ADS records
│       ├── ApJ_ads_raw.json
│       ├── A&A_ads_raw.json
│       ├── ApJL_ads_raw.json
│       ├── ApJS_ads_raw.json
│       ├── JCAP_ads_raw.json
│       ├── arxiv_meta.jsonl          # Shared arXiv metadata (keyed by arXiv ID)
│       └── failed_ids_*.txt          # IDs that failed arXiv fetch (for retry)
│
└── results/
    └── <JOURNAL>/
        ├── RESULTS.md                # Summary table and findings
        ├── fig{1..10}.pdf            # Publication-quality figures
        ├── fig{1..10}.png            # High-res raster
        └── *.csv                     # Detailed per-day statistics
```
 
## Installation from Environment
 
If you don't have conda or prefer to install manually:
 
```bash
pip install numpy pandas matplotlib scipy requests lxml
 
# Or with conda:
conda install -c conda-forge numpy pandas matplotlib scipy requests lxml
```
 
## Usage
 
### Analyse a Single Journal
 
```bash
python run_pipeline.py --journal MNRAS
```
 
The pipeline will:
1. Load cached ADS records (or fetch if `ADS_API_TOKEN` is set)
2. Fetch arXiv metadata for all papers without it
3. Filter to astro-ph primary papers
4. Assign submission and announcement days (UTC → US Eastern, DST-aware)
5. Compute median citations, bootstrap CIs, statistical tests per day
6. Generate 10 figures and a summary
### Generate Paper Figures (6-panel)
 
```bash
python make_paper_figures.py
```
 
Produces three publication figures in `results/paper_figures/`:
- `fig_hist_weekend_6panel.{pdf,png}` — Citation distributions (log-binned histograms)
- `fig_cdf_weekend_6panel.{pdf,png}` — Cumulative distributions
- `fig_median_announcement_6panel.{pdf,png}` — Medians by announcement day with bootstrap CIs
All figures include grayscale-safe styling (linestyle + shading, not color alone) for print reproduction.
 
### Run Tests
 
```bash
pytest tests/test_schedule.py -v
```
 
Tests validate day-of-week assignment logic against daylight-saving transitions, live arXiv API, and independent re-implementation.
 
## Data
 
### Sources
 
- **NASA Astrophysics Data System (ADS):** Citation counts for refereed articles (2020–2023)
- **arXiv API:** Preprint submission timestamps and primary category
### Caching Strategy
 
Raw data is cached locally to avoid repeated API calls:
 
- `data/raw/<JOURNAL>_ads_raw.json` — ADS records per journal (stored as-is from API)
- `data/raw/arxiv_meta.jsonl` — arXiv metadata (one JSON record per line, keyed by arXiv ID)
**To re-fetch:** Delete the cache files and set `ADS_API_TOKEN`:
```bash
rm data/raw/*.json data/raw/*.jsonl
export ADS_API_TOKEN="your-token-here"
python run_pipeline.py --journal MNRAS
```
 
### Data Retrieval
 
ADS queries use the following filters:
```
bibstem:<JOURNAL> year:2020-2023 property:refereed doctype:article
```
 
arXiv filtering: only papers with `primary_category` starting with `astro-ph` are included.
 
## Methodology
 
### Day-of-Week Assignment
 
arXiv operates on a 14:00 ET (US Eastern) submission deadline with no weekend announcements:
 
- **Submission day:** UTC timestamp converted to US Eastern (using IANA timezone database for DST)
- **Announcement day:** 
  - Friday 14:00 ET – Sunday 23:59 ET → announced Sunday 20:00 ET → labeled "Friday"
  - Monday 00:00 ET – Monday 14:00 ET → announced Monday 20:00 ET → labeled "Monday"
  - Monday 14:00 ET – Friday 14:00 ET → announced same day → labeled by submission day
Validation: 22 unit tests + independent re-implementation + arXiv API re-fetch agreement.
 
### Statistics
 
**Primary:** Median citation count per group, 95% percentile-bootstrap confidence intervals (10,000 resamples, seed=42)
 
**Secondary:** Mean (for comparison), Kruskal–Wallis test across days, Mann–Whitney *U* test (weekend vs. weekday)
 
**Robustness:** Year-stratified analysis and year-normalised citations
 
Median is primary because citation distributions are strongly right-skewed; the mean is dominated by a small number of highly cited papers.
 
## Results Summary
 
| Journal | N | Weekend N | Weekend Median | Weekday Median | MW *p* | Significant? |
|---------|---|-----------|----------------|----------------|--------|--------------|
| MNRAS   | 14,338 | 983 | 13 | 16 | 3.9×10⁻¹³ | ✓ |
| ApJ     | 10,153 | 929 | 14 | 18 | 1.3×10⁻⁹ | ✓ |
| A&A     | 7,886  | 555 | 15 | 18 | 7.2×10⁻⁶ | ✓ |
| ApJL    | 2,325  | 218 | 22 | 25 | 0.020 | ✓ |
| ApJS    | 893    | 87  | 17 | 23 | 5.7×10⁻⁴ | ✓ |
| JCAP    | 1,578  | 104 | 15 | 19 | 0.15 | — |
 
**Conclusion:** Weekend submissions receive 12–26% lower median citations. Median citations are indistinguishable across Monday–Friday.
 
## Citation
 
If you use this pipeline or data, please cite:
 
```bibtex
@article{Sharma2026,
  author = {Sharma, C. and Desai, S.},
  title = {Which is the best day of the week to submit to arXiv:astro-ph?},
  journal = {[To be submitted]},
  year = {2026},
  eprint = {[arXiv pending]},
  url = {https://github.com/chirag003214/astroph-weekday-citations}
}
```
 
## Contact
 
- **Chirag Sharma** — IIT Kharagpur, Department of Physics (csharma@kgpian.iitkgp.ac.in)
- **Shantanu Desai** — IIT Hyderabad, Department of Physics
## License
 
MIT
 
## Acknowledgments
 
This analysis uses data from the NASA Astrophysics Data System and the arXiv preprint repository. We thank both services for their open-access APIs and data.
 
---
 
**Last updated:** August 2026  
**Repository:** https://github.com/chirag003214/astroph-weekday-citations
