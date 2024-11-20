
# ArduPilot BIN File Parser, Cleaner, and Analyzer

## Overview
This Python script processes ArduPilot `.bin` files, converts them into `.csv` files, cleans the data, and analyzes it. The tool provides an efficient workflow for handling large sets of log data, cleaning it by removing unnecessary columns, and producing detailed insights.

Key features include:
- **BIN to CSV conversion**: Parses `.bin` files into structured `.csv` files.
- **Data cleaning**: Removes columns with all missing values or constant values.
- **Analysis and statistics**: Displays key metrics, missing value analysis, and duplicates in a formatted terminal output.
- **User-friendly terminal interface**: Uses the `rich` library for clean, styled terminal output.

---

## Features
1. **BIN to CSV Parsing**:
   - Reads `.bin` log files using the `pymavlink` library.
   - Converts parsed messages into a `pandas` DataFrame.
   - Saves the DataFrame as a raw `.csv` file.

2. **Data Cleaning**:
   - Groups data by `mavpackettype`.
   - Drops columns with all missing values or constant values.
   - Combines and saves cleaned data into a new `.csv` file.

3. **Data Analysis**:
   - Provides:
     - Total rows and columns.
     - Number of duplicate rows.
   - Identifies and removes redundant or problematic columns.

4. **Directory Structure**:
   - **Input**: All `.bin` files should be placed in the `logs/bin` directory.
   - **Output**:
     - Raw CSVs are saved in `logs/raw` (prefixed with `RAW_`).
     - Cleaned CSVs are saved in `logs/clean` (prefixed with `CLEAN_`).

---

## Requirements
### Python Packages
- `pandas`: For data manipulation.
- `pymavlink`: For parsing ArduPilot `.bin` files.
- `rich`: For styled terminal output.

### Installation
Install the required packages:
```bash
pip install pandas pymavlink rich
```

---

## Directory Structure
Ensure the following directory structure exists:
```
logs/
├── bin/       # Place all .bin files here
├── raw/       # Raw CSV files will be saved here
└── clean/     # Cleaned CSV files will be saved here
```

---

## Usage
### Step 1: Place `.bin` Files
Place all `.bin` files to be processed in the `logs/bin` directory.

### Step 2: Run the Script
Run the script from the terminal:
```bash
python process_logs.py
```

### Step 3: View Results
- **Raw CSVs**: Located in the `logs/raw` directory (prefixed with `RAW_`).
- **Cleaned CSVs**: Located in the `logs/clean` directory (prefixed with `CLEAN_`).
- **Analysis Output**: Displayed in the terminal.

---

## Code Walkthrough
### Main Components

#### 1. Parsing BIN Files
The `parse_bin_to_dataframe` function:
- Reads messages from a `.bin` file.
- Converts them to a `pandas` DataFrame.
- Saves the raw data as a CSV.

```python
def parse_bin_to_dataframe(bin_path, csv_path):
    log = mavutil.mavlink_connection(bin_path)
    messages = []
    with Progress(...):
        while True:
            msg = log.recv_match()
            if msg is None:
                break
            messages.append(msg.to_dict())
    df = pd.DataFrame(messages)
    df.to_csv(csv_path, index=False)
    return df
```

#### 2. Cleaning Data
The `clean_and_combine_data` function:
- Groups the DataFrame by `mavpackettype`.
- Drops all-null columns.
- Combines cleaned data into a single DataFrame.

```python
def clean_and_combine_data(df):
    grouped = df.groupby('mavpackettype')
    combined_df = pd.DataFrame()
    for packet_type, group_df in grouped:
        all_null_columns = group_df.columns[group_df.isnull().all()]
        group_df_cleaned = group_df.drop(columns=all_null_columns)
        combined_df = pd.concat([combined_df, group_df_cleaned], axis=0)
    return combined_df
```

#### 3. Analyzing Data
The `analyze_dataframe` function:
- Displays total rows and columns.
- Identifies and removes constant columns.
- Counts duplicate rows.

```python
def analyze_dataframe(df):
    constant_columns = [col for col in df.columns if df[col].nunique() == 1]
    df = df.drop(columns=constant_columns)
    console.print(f"Total Rows: {df.shape[0]}")
    console.print(f"Total Columns: {df.shape[1]}")
    duplicate_count = df.duplicated().sum()
    console.print(f"Duplicate Rows: {duplicate_count}")
```

---

## Example Terminal Output
```plaintext
📂 Processing BIN file: log_24.bin
Parsing log_24.bin: 100% |███████████████████████████| 10,000/10,000 [00:10<00:00]
✔️ Saved RAW CSV to logs/raw/RAW_log_24.csv

📦 Unique mavpackettypes: 15
Cleaning packet types: 100% |████████████████████████| 15/15 [00:02<00:00]
✔️ Cleaned and combined DataFrame with 20,000 rows and 50 columns

🔍 Analyzing DataFrame...
🗑️ Dropped constant columns: 5
Total Rows: 20,000
Total Columns: 45
Duplicate Rows: 50
✔️ Saved CLEAN CSV to logs/clean/CLEAN_log_24.csv
```

---

## Customization
You can modify:
1. **Directories**: Change the `logs_dir`, `bin_dir`, `raw_dir`, or `clean_dir` paths.
2. **Column Filtering**: Customize which columns to drop during cleaning in `clean_and_combine_data`.
3. **Additional Analysis**: Add more statistics or visualizations to `analyze_dataframe`.

---

## Support
If you encounter any issues, ensure the required directories exist, and dependencies are installed. For additional help, feel free to reach out!
