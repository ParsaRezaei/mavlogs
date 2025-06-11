import os
import pandas as pd
from pymavlink import mavutil
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table

console = Console()

# Function to parse BIN file into a DataFrame
def parse_bin_to_dataframe(bin_path, csv_path):
    """
    Converts an ArduPilot BIN file into a CSV and DataFrame.
    
    Args:
        bin_path (str): Path to the BIN file.
        csv_path (str): Path to save the CSV file.

    Returns:
        pd.DataFrame: Parsed data as a pandas DataFrame.
    """
    log = mavutil.mavlink_connection(bin_path)
    messages = []

    # Parse the log messages
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task(f"Parsing {os.path.basename(bin_path)}", total=None)
        while True:
            msg = log.recv_match()
            if msg is None:
                break
            messages.append(msg.to_dict())
            progress.update(task, advance=1)

    # Convert to DataFrame and save to CSV
    df = pd.DataFrame(messages)
    df.to_csv(csv_path, index=False)
    console.print(f"✔️ [green]Saved RAW CSV to {csv_path}[/green]")
    return df

# Function to clean and combine DataFrames by packet type
def clean_and_combine_data(df):
    """
    Cleans the DataFrame by dropping all-null columns and combining data by mavpackettype.

    Args:
        df (pd.DataFrame): Original DataFrame from CSV.

    Returns:
        pd.DataFrame: Cleaned and combined DataFrame.
    """
    packet_types = df['mavpackettype'].unique()
    console.print(f"📦 [cyan]Unique mavpackettypes: {len(packet_types)}[/cyan]")

    grouped = df.groupby('mavpackettype')
    combined_df = pd.DataFrame()

    # Process each packet type
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task("Cleaning packet types", total=len(packet_types))
        for packet_type, group_df in grouped:
            all_null_columns = group_df.columns[group_df.isnull().all()].tolist()
            group_df_cleaned = group_df.drop(columns=all_null_columns)
            group_df_cleaned['mavpackettype'] = packet_type
            combined_df = pd.concat([combined_df, group_df_cleaned], axis=0, ignore_index=True)
            progress.update(task, advance=1)

    console.print(
        f"✔️ [green]Cleaned and combined DataFrame with {combined_df.shape[0]} rows and {combined_df.shape[1]} columns[/green]"
    )
    return combined_df

# Function to analyze the cleaned DataFrame
def analyze_dataframe(df):
    """
    Performs analysis on the DataFrame to display key statistics and identify potential issues.

    Args:
        df (pd.DataFrame): Cleaned DataFrame.
    """
    console.print("🔍 [bold yellow]Analyzing DataFrame...[/bold yellow]")

    # Drop constant columns
    constant_columns = [col for col in df.columns if df[col].nunique() == 1]
    df = df.drop(columns=constant_columns)
    console.print(f"🗑️ [red]Dropped constant columns: {len(constant_columns)}[/red]")

    # General stats as a table
    table = Table(title="DataFrame Overview", show_header=True, header_style="bold magenta")
    table.add_column("Metric", justify="right")
    table.add_column("Value")
    table.add_row("Total Rows", str(df.shape[0]))
    table.add_row("Total Columns", str(df.shape[1]))
    console.print(table)

    # # Missing value stats
    # null_counts = df.isnull().sum()
    # missing_table = Table(title="Missing Values", show_header=True, header_style="bold cyan")
    # missing_table.add_column("Column")
    # missing_table.add_column("Missing Values", justify="right")
    # for col, count in null_counts[null_counts > 0].items():
    #     missing_table.add_row(col, str(count))
    
    # # Display the missing values table only if there are missing values
    # if len(missing_table.rows) > 0:
    #     console.print(missing_table)
    # else:
    #     console.print("✔️ [green]No missing values detected.[/green]")

    # Display duplicate row count
    duplicate_count = df.duplicated().sum()
    console.print(f"🔁 [blue]Number of duplicate rows: {duplicate_count}[/blue]")

# Main script logic
if __name__ == "__main__":
    # Directories
    logs_dir = "./logs"
    bin_dir = os.path.join(logs_dir, "bin")
    raw_dir = os.path.join(logs_dir, "raw")
    clean_dir = os.path.join(logs_dir, "clean")

    # Check if logs directory exists
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir, exist_ok=True)
        os.makedirs(bin_dir, exist_ok=True)
        console.print(f"[red]Created missing 'logs' and 'logs/bin' directories. Please add your BIN files to 'logs/bin' and try again.[/red]")
        exit(1)

    # Create output directories if they don't exist
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(clean_dir, exist_ok=True)

    # Process each BIN file in the bin_dir
    bin_files = [f for f in os.listdir(bin_dir) if f.endswith(".bin")]

    with console.status("[bold][green]Processing BIN files...", spinner="dots"):
        for bin_file in bin_files:
            bin_path = os.path.join(bin_dir, bin_file)
            raw_csv_path = os.path.join(raw_dir, f"RAW_{os.path.splitext(bin_file)[0]}.csv")
            clean_csv_path = os.path.join(clean_dir, f"CLEAN_{os.path.splitext(bin_file)[0]}.csv")

            console.print(f"\n📂 [bold][green]Processing BIN file:[/bold][/green] {bin_file}")

            # Step 1: Parse BIN file
            df = parse_bin_to_dataframe(bin_path, raw_csv_path)

            # Step 2: Clean and combine data
            combined_df = clean_and_combine_data(df)

            # Step 3: Analyze the cleaned DataFrame
            analyze_dataframe(combined_df)

            # Step 4: Save cleaned DataFrame
            combined_df.to_csv(clean_csv_path, index=False)
            console.print(f"✔️ [green]Saved CLEAN CSV to {clean_csv_path}[/green]")
