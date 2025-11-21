# WikiPharm Citation Fixer

**Automated Wikipedia citation formatting for Pharmacology Wikipedia articles**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![WikiProject: Pharmacology](https://img.shields.io/badge/WikiProject-Pharmacology-blue.svg)](https://en.wikipedia.org/wiki/Wikipedia:WikiProject_Pharmacology)

---

## Overview

WikiPharm Citation Fixer is a simple CMD tool designed for to streamline the formatting and enhancement of `{{Cite journal}}` templates in Pharmacology Wikipedia articles.

> **⚠️ Warning**: Excessive use of such tools may render [Boghog](https://en.wikipedia.org/wiki/User:Boghog) obsolete

---

## Features

### ✅ Author Formatting
- Converts `|last=` and `|first=` parameters to compact `|vauthors=` Vancouver format
- Limits initials to **2 maximum** per author (e.g., "Smith AB" not "Smith ABC")
- Handles up to 6 authors with "et al" for longer author lists

### 📅 Date Standardization
- Converts ISO dates (`2024-11-12`) → `November 2024`
- Removes day from existing dates → `November 12, 2024` → `November 2024`
- Preserves year-only dates

### 🔍 Metadata Enrichment
- **ISSN**: Retrieved from CrossRef API using DOI
- **PMID**: Retrieved from NCBI E-utilities using DOI
- **PMC**: Retrieved from NCBI PMC ID Converter using PMID

### ⚙️ Two Operating Modes
1. **Incremental Mode** (default): Only adds missing identifiers
2. **Force Refresh Mode**: Re-fetches and updates all identifiers from APIs

---

## Installation

### Requirements
- Python 3.10 or higher
- `requests` library

### Setup

```bash
# Clone the repository
git clone https://github.com/wolren/wikipharm-citation-fixer.git
cd wikipharm-citation-fixer

# Install dependencies
pip install -r requirements.txt

# Run the script
python wikipharm_fixer.py
```

---

## Usage

### Basic Usage (Incremental Mode)

```bash
python wikipharm_fixer.py
```

This will:
1. Read citations from `paste.txt`
2. Add missing ISSN, PMID, and PMC identifiers
3. Convert authors to Vancouver format
4. Fix date formatting
5. Save fixed citations to `paste_corrected.txt`

### Force Refresh Mode

```bash
python wikipharm_fixer.py --force
```

This will re-fetch **all** identifiers (ISSN, PMID, PMC) even if they already exist in citations, useful for updating outdated or incorrect metadata.

### Input/Output Files

- **Input**: `paste.txt` (place your Wikipedia wikitext with `{{Cite journal}}` templates here)
- **Output**: `paste_corrected.txt` (fixed citations will be saved here)

---

## Example

### Before
```wiki
{{Cite journal|last=Smith|first=John A.|last2=Doe|first2=Jane B. C.|date=2024-11-12|title=Example Article|journal=Nature|volume=500|pages=123-456|doi=10.1038/nature12345}}
```

### After
```wiki
{{cite journal | vauthors = Smith JA, Doe JB | date = November 2024 | title = Example Article | journal = Nature | volume = 500 | pages = 123-456 | doi = 10.1038/nature12345 | issn = 0028-0836 | pmid = 12345678 | pmc = 9876543}}
```

---

## Configuration

`ApiConfig`:

```python
@dataclass(frozen=True)
class ApiConfig:
    user_agent: str = "WikiPharmCitationFixer/2.0"
    ncbi_tool: str = "WikiPharmCitationFixer"
    api_delay: float = 0.34   # NCBI rate limit: ~3 requests/second
    crossref_delay: float = 0.05  # CrossRef: 50 requests/second
```
---

No email configuration is required for API access.

## API Rate Limiting

The tool respects API rate limits:
- **NCBI E-utilities**: 3 requests per second
- **CrossRef**: 50 requests per second (polite pool)

---

## Command-Line Options

| Option | Description |
|--------|-------------|
| _(none)_ | Incremental mode (default): add missing fields only |
| `--force`, `-f` | Force refresh mode: re-fetch all identifiers |
| `force`, `refresh`, `all` | Alternative keywords for force refresh |

---

## Contributing

Contributions are welcome! This tool was developed for WikiProject Pharmacology but can be adapted for other Wikipedia projects.

### To contribute:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Open a Pull Request

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---
