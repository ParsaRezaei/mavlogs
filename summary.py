#!/usr/bin/env python3
"""
summary.py – Generate summary reports and plots from ArduPilot “clean” CSV logs.

NEW:
  • --dir <folder>     Process every *.csv in <folder>.
  • --outroot <folder> Put all per-log outputs in <folder> (default: processed_logs).
    Each log is written to <outroot>/<ID>/… where <ID> is the number captured
    from “log_<ID>” (e.g. log_007_xyz.csv → processed_logs/007/) or, if no
    numeric ID exists, the stem of the file name.

If --csv is given, the script behaves exactly as before.
"""

import re
import os
import glob
import argparse
import pandas as pd
import numpy as np
import zipfile
import matplotlib.pyplot as plt

# ─────────────────────────── helper: plotting ──────────────────────────── #
def save_plot(x, ys, title, xlabel, ylabel, filename, labels=None, data_csv=None):
    plt.figure()
    if isinstance(ys, pd.DataFrame):
        for col in ys.columns:
            plt.plot(x, ys[col], label=col)
        if labels is None:
            plt.legend()
        if data_csv:
            df_out = ys.copy()
            df_out.insert(0, xlabel, x)
            df_out.to_csv(data_csv, index=False)
    else:
        plt.plot(x, ys)
        if data_csv:
            pd.DataFrame({xlabel: x, ylabel: ys}).to_csv(data_csv, index=False)

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

# ─────────────────────────── core per-log work ─────────────────────────── #
def analyze_log(csv_path, param_glossary_path, subsys_path, output_dir="log_output"):
    """Unchanged: generate one report tree for a single cleaned CSV."""
    df = pd.read_csv(csv_path, low_memory=False)
    os.makedirs(output_dir, exist_ok=True)

    # === Summary ===
    summary = {
        "Flight Duration (s)": df["TimeUS"].iloc[-1] / 1e6,
        "Max Altitude (m)": df["Alt"].max(),
        "Min Voltage (V)": df["Volt"].min(),
        "Max Voltage (V)": df["Volt"].max(),
        "Avg Current (A)": df["Curr"].mean(),
        "Max Current (A)": df["Curr"].max(),
        "Max Vibration": df[["VibeX", "VibeY", "VibeZ"]].max().max(),
        "Max Roll": df["Roll"].abs().max(),
        "Max Pitch": df["Pitch"].abs().max()
    }
    pd.DataFrame(summary.items(), columns=["Metric", "Value"]).to_csv(
        f"{output_dir}/summary.csv", index=False
    )

    # === Parameter Glossary ===
    pd.read_excel(param_glossary_path).to_csv(
        f"{output_dir}/parameter_glossary.csv", index=False
    )

    # === Subsys + ECode Report ===
    subsys_df = pd.read_excel(subsys_path)
    if {"Subsys", "ECode"}.issubset(df.columns):
        errs = df[df["Subsys"].notna() & df["ECode"].notna()][
            ["TimeUS", "Subsys", "ECode"]
        ].copy()
        errs["Subsys"] = errs["Subsys"].astype(int)
        errs["ECode"] = errs["ECode"].astype(int)
        merged = errs.merge(subsys_df, how="left", on=["Subsys", "ECode"])
        merged.to_csv(f"{output_dir}/subsys_ecode_report.csv", index=False)

    # === STATUSTEXT Messages ===
    df[df["mavpackettype"] == "MSG"].to_csv(
        f"{output_dir}/status_text_log.csv", index=False
    )

    # === Failsafe Flags ===
    if "FailFlags" in df.columns:
        fs_df = df[df["FailFlags"].notna()][["TimeUS", "FailFlags"]].copy()
        fs_df["FailFlags"] = fs_df["FailFlags"].astype(int)
        fs_df["Radio FS"] = fs_df["FailFlags"].apply(lambda x: bool(x & 0x01))
        fs_df["Battery FS"] = fs_df["FailFlags"].apply(lambda x: bool(x & 0x02))
        fs_df["GCS FS"] = fs_df["FailFlags"].apply(lambda x: bool(x & 0x04))
        fs_df.to_csv(f"{output_dir}/failsafe_report.csv", index=False)

    # === Anomaly Flags ===
    flags = pd.DataFrame()
    flags["TimeUS"] = df["TimeUS"]
    flags["High Vibration"] = df[["VibeX", "VibeY", "VibeZ"]].max(axis=1) > 30
    flags["Low Voltage"] = df["Volt"] < 10.5
    flags["High Current"] = df["Curr"] > 50
    flags["GPS Loss"] = df["NSats"] < 6
    flags.to_csv(f"{output_dir}/anomaly_flags.csv", index=False)

    # === Plots + CSV Data ===
    plot_dir = os.path.join(output_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    save_plot(
        df["TimeUS"] / 1e6,
        df["Alt"],
        "Altitude vs Time",
        "Time (s)",
        "Altitude (m)",
        f"{plot_dir}/altitude_vs_time.png",
        data_csv=f"{plot_dir}/altitude_vs_time.csv",
    )
    save_plot(
        df["Alt"],
        df["ThO"],
        "Throttle vs Altitude",
        "Altitude (m)",
        "Throttle Output",
        f"{plot_dir}/throttle_vs_altitude.png",
        data_csv=f"{plot_dir}/throttle_vs_altitude.csv",
    )
    save_plot(
        df["Lng"],
        df["Lat"],
        "GPS Path",
        "Longitude",
        "Latitude",
        f"{plot_dir}/gps_path_2d.png",
        data_csv=f"{plot_dir}/gps_path_2d.csv",
    )
    save_plot(
        df["TimeUS"] / 1e6,
        df[["Roll", "Pitch", "Yaw"]],
        "Attitude",
        "Time (s)",
        "Degrees",
        f"{plot_dir}/roll_pitch_yaw.png",
        data_csv=f"{plot_dir}/roll_pitch_yaw.csv",
    )
    save_plot(
        df["TimeUS"] / 1e6,
        df[["VibeX", "VibeY", "VibeZ"]],
        "Vibration",
        "Time (s)",
        "Level",
        f"{plot_dir}/vibration_plot.png",
        data_csv=f"{plot_dir}/vibration_plot.csv",
    )

    # === Zip all output ===
    zip_path = os.path.abspath(f"{output_dir}/full_export.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for f in files:
                full = os.path.join(root, f)
                # Avoid self-inclusion by comparing absolute paths
                if os.path.abspath(full) != zip_path:
                    zf.write(full, os.path.relpath(full, output_dir))

# ─────────────────────────── batch runner ──────────────────────────────── #
def extract_log_id(fname: str) -> str:
    """
    Return the numeric token after 'log_' (e.g. '007' in log_007_clean.csv).
    Falls back to stem if no numeric ID is present.
    """
    m = re.search(r"log_(\d{1,})", fname)
    return m.group(1) if m else os.path.splitext(os.path.basename(fname))[0]

def process_directory(input_dir, param_glossary, subsys, out_root="processed_logs"):
    csv_files = glob.glob(os.path.join(input_dir, "*.csv"))
    if not csv_files:
        print(f"⚠️  No CSV files found in {input_dir}")
        return

    os.makedirs(out_root, exist_ok=True)

    for csv_path in csv_files:
        log_id = extract_log_id(csv_path)
        out_dir = os.path.join(out_root, log_id)
        print(f"→ Processing {os.path.basename(csv_path)} → {out_dir}")
        analyze_log(csv_path, param_glossary, subsys, out_dir)

# ─────────────────────────── CLI entry-point ──────────────────────────── #
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate summaries from ArduPilot logs.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--csv", help="Path to a single cleaned ArduPilot CSV log")
    mode.add_argument("--dir", help="Folder containing multiple cleaned CSV logs")

    ap.add_argument("--glossary", default="params.csv", help="Path to parameter glossary")
    ap.add_argument("--subsys", default="subSys_err.csv", help="Path to Subsys+ECode decoder")
    ap.add_argument("--out", default=None, help="Output folder (single-file mode)")
    ap.add_argument("--outroot", default="./logs/reports",
                    help="Root folder for batch mode outputs (default: ./logs/reports)")

    args = ap.parse_args()

    if args.csv:
        out_dir = args.out if args.out else os.path.splitext(args.csv)[0] + "_output"
        analyze_log(args.csv, args.glossary, args.subsys, out_dir)
    else:
        process_directory(args.dir, args.glossary, args.subsys, args.outroot)
