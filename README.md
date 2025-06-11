# ArduPilot BIN File Parser, Cleaner, and Analyzer

## Overview

This Python toolchain converts ArduPilot log files into tidy datasets, cleans them, and produces quick‑look analytics. It is designed for large log sets and emphasises terminal‑first ergonomics using the **rich** library for styled output.

Key capabilities

* **BIN → CSV** conversion via *pymavlink*
* Column pruning (all‑null & constant)
* One‑command batch processing of an entire *logs/bin* folder
* Lightweight descriptive statistics & anomaly flags
* Clearly organised output directories (raw, clean, reports, plots)

---

## Features

1. **BIN → CSV Parsing** – reads each log with  *pymavlink* , streams messages into a `pandas.DataFrame`, then persists `RAW_<name>.csv` to  *logs/raw* .
2. **Data Cleaning** – groups by `mavpackettype`, removes empty & constant columns, and writes a consolidated `CLEAN_<name>.csv` to  *logs/clean* .
3. **Quick Analysis** – prints row/column counts, duplicate counts, and drops constant columns in‑place.
4. **Progress‑Aware CLI** – rich progress bars keep long conversions transparent.

---

## Requirements

### Option A — install via *requirements.txt*

```bash
pip install -r requirements.txt
```

### Option B — one‑liner

```bash
pip install pandas numpy pymavlink rich matplotlib openpyxl
```

> Tested with **Python 3.9+** on Linux and macOS.

```
pandas>=2.0
numpy>=1.25
pymavlink>=2.4
rich>=13.0
matplotlib>=3.7
openpyxl>=3.1
```

---

## Directory Layout

```
logs/
├── bin/      # place .bin files here
├── raw/      # RAW_*.csv written here
├── clean/    # CLEAN_*.csv written here
└── reports/  # summary statistics & decoded tables (auto‑created)


## Python Scripts

| Script                              | Purpose                                                                                                                                                                                                                                   |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `logs.py` | End‑to‑end pipeline that converts ``** → RAW CSV → CLEAN CSV**, prints rich‑style stats, and stores artefacts under `logs/raw`,`logs/clean`.                                                                                     |
| `summary.py`                      | Post‑processing helper that ingests**CLEAN CSV**files plus parameter glossaries to generate summaries, decoded error tables, anomaly flags, and share‑ready plots. Accepts single files (`--csv`) or whole folders (`--dir`). |

---

## Usage

```bash
# 1. drop .bin files into logs/bin
python process_logs.py         # 2. run the script
                          # 3. read the rich output or open files in logs/
```

---

## Generated Reports & Artefacts

After each run the script assembles a small bundle of value‑added artefacts inside ``.  The following table describes the contents (adapted from  *README.txt* ):

| # | File                                                                | Purpose                                                                                                                       |
| - | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| 1 | `params.csv`/ **origin** :*Parameter_sheet.xlsx*          | Filtered glossary of every ArduPilot parameter (name, units, category, description). Useful for look‑ups & dashboard labels. |
| 2 | `subSys_err.csv`/ **origin** :*SubSys_ErrCode_Sheet.xlsx* | Decoded mapping of `Subsys`+`ECode`pairs to human‑readable subsystem fault descriptions.                                 |
| 3 | `summary.csv`                                                     | High‑level flight statistics – duration, max altitude/voltage/current, mean current draw, vibration, max roll/pitch etc.    |

## Example Session

```text
📂 Scanning logs/bin — found 3 files

🔄 Converting  log_42.bin … 10,000/10,000 [00:09] ✅ RAW_log_42.csv
🧹 Cleaning data … 15 packet types processed [00:02] ✅ CLEAN_log_42.csv
📊 Summary written : reports/summary.csv
⚠️ 0 failsafe events • 3 STATUSTEXT warnings decoded
📈 Plots saved      : reports/plots/
```

## Quick‑Start: `summary.py`

### 1. Install prerequisites (first run only)

```bash
python3 -m venv logenv          # optional but recommended
source logenv/bin/activate
pip install pandas matplotlib numpy openpyxl
```

### 2. Put the required files together

```
project_folder/
├── summary.py
├── params.csv          ← parameter glossary
└── subSys_err.csv     ← SubSys + ECode decoder
```

### 3. Process a single log (spot‑check)

```bash
python summary.py \
  --csv cleaned_logs/log_001_clean.csv \
  --glossary Parameter_sheet.xlsx \
  --subsys SubSys_ErrCode_Sheet.xlsx
```

• Outputs land in `log_output/` (or change with `--out my_folder`).

### 4. Batch‑process a folder

```bash
python summary.py \
  --dir cleaned_logs \
  --glossary Parameter_sheet.xlsx \
  --subsys SubSys_ErrCode_Sheet.xlsx \
  --outroot processed_logs
```

• Each CSV gets its own folder: `processed_logs/<ID>/…`.

### 5. What’s inside each output folder

| File               | Purpose                                               |
| ------------------ | ----------------------------------------------------- |
| `summary.csv`    | Flight duration, battery min/max, vibration peaks, … |
| `params.csv`     | Decoded parameters (filtered glossary)                |
| `subSys_err.csv` | `Subsys`/`ECode`ERR events, human‑readable       |

### 6. Common tweaks

* **Custom out folder (single log)** – `--out my_folder`
* **Different batch root** – `--outroot my_processed_logs`
* **Quiet run inside a script** – `python summary.py … > run.log 2>&1`

### 7. Troubleshooting

* **“No CSV files found”** – check `--dir` path and file extensions.
* **ImportError** – ensure the *pip install* step ran inside the venv.
* **Empty plots** – log may lack needed columns (Alt, Volt, VibeX…).
