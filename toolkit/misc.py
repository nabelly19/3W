"""This is the 3W Toolkit's miscellaneous sub-module.

All resources that do not fit in the other sub-modules are define here.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
import os
import dask.dataframe as dd

from matplotlib.patches import Patch
from pathlib import Path
from multiprocessing.dummy import Pool as ThreadPool
from collections import defaultdict
from natsort import natsorted

import warnings

warnings.simplefilter("ignore", FutureWarning)
import plotly.offline as py
import plotly.graph_objs as go
import glob
import pandas as pd
from tslearn.preprocessing import TimeSeriesScalerMeanVariance

from .base import (
    COLUMNS_DATA_FILES,
    LABELS_DESCRIPTIONS,
    PATH_DATASET,
    VARS,
    EVENT_NAMES,
    PARQUET_EXTENSION,
    PARQUET_ENGINE,
)

folder_mapping = {
    0: 'Normal Operation', 1: 'Abrupt Increase of BSW', 2: 'Spurious Closure of DHSV',
    3: 'Severe Slugging', 4: 'Flow Instability', 5: 'Rapid Productivity Loss',
    6: 'Quick Restriction in PCK', 7: 'Scaling in PCK', 8: 'Hydrate in Production Line',
    9: 'Hydrate in Service Line'
}


# Methods
#

def load_and_combine_data(dataset_dir, datatype):
    """
    Loads and combines Parquet files from multiple folders, adding additional columns 
    for folder ID, date, and time extracted from the file names.

    Args:
    ----------
    dataset_dir : str
        Path to the root directory containing subfolders (0 to 9) with Parquet files.

    datatype : str
        Type that user need to remove of the dataset for a specific analysis

    Returns:
    --------
    dask.DataFrame or None
        A combined Dask DataFrame with all the data from the Parquet files, or None 
        if no files were found.
    
    Functionality:
    --------------
    - Iterates through folders (0-9) and loads all valid Parquet files (ignoring those 
      starting with 'SIMULATED' or other type defined by user).
    - Extracts date and time from the filename and adds them as new columns ('data', 'hora').
    - Adds a 'folder_id' column to identify the folder each file originated from.
    
    Example:
    --------
    df = load_and_combine_data('/path/to/dataset')
    """
    dfs = []
    for folder in range(10):
        folder_path = os.path.join(dataset_dir, str(folder))
        if os.path.exists(folder_path):
            for file_name in os.listdir(folder_path):
                if file_name.endswith('.parquet') and not file_name.startswith(datatype): #removal according to the user's wishes
                    df = dd.read_parquet(os.path.join(folder_path, file_name))
                    file_name_without_ext = os.path.splitext(file_name)[0] 
                    date_str = file_name_without_ext.split.split('_')[1]
                    formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    formatted_time = f"{date_str[8:10]}:{date_str[10:12]}:{date_str[12:]}"
                    df = df.assign(folder_id=folder, data=formatted_date, hora=formatted_time)
                    dfs.append(df)
    return dd.concat(dfs) if dfs else None

def classify_events(df):
    """
    Classifies events in the dataset by folder and event type, and summarizes the 
    occurrences of different event types.

    Args:
    ----------
    df : dask.DataFrame
        The DataFrame containing the event data, including a 'folder_id' column and a 'class' column.

    Returns:
    --------
    dict
        A dictionary summarizing the count of events by event type ('Normal Operation', 
        'Transient', 'Permanent Anomaly') for each folder.
    
    Functionality:
    --------------
    - For each folder (0-9), counts the occurrences of events in three categories:
      - 'Normal Operation': Events classified as 0.
      - 'Transient': Events classified between 1 and 9.
      - 'Permanent Anomaly': Events classified between 101 and 109.
    
    Example:
    --------
    event_summary = classify_events(df)
    """
    data = {folder_mapping[i]: {'Normal Operation': 0, 'Transient': 0, 'Permanent Anomaly': 0} for i in range(10)}
    for folder in range(10):
        folder_data = df[df['folder_id'] == folder]
        if len(folder_data.index) > 0:
            dtb = folder_data['class'].value_counts().compute()
            data[folder_mapping[folder]]['Normal Operation'] = dtb.get(0, 0)
            data[folder_mapping[folder]]['Transient'] = dtb[(dtb.index >= 1) & (dtb.index <= 9)].sum()
            data[folder_mapping[folder]]['Permanent Anomaly'] = dtb[(dtb.index >= 101) & (dtb.index <= 109)].sum()
    return data

def visualize_data(data):
    """
    Visualizes the event distribution by type using a stacked area chart.

    Parameters:
    ----------
    data : dict
        A dictionary where keys are folder names, and values are dictionaries with 
        counts of different event types ('Normal Operation', 'Transient', 'Permanent Anomaly').

    Returns:
    --------
    None
        Displays a stacked area chart showing the distribution of event types for each folder.
    
    Functionality:
    --------------
    - Converts the input dictionary into a DataFrame for plotting.
    - Generates a stacked area chart with event types represented in different colors.
    - Adds labels for the x and y axes, and a title.
    
    Example:
    --------
    visualize_data(event_summary)
    """
    df_plot = pd.DataFrame(data).T
    df_plot.plot(kind='area', stacked=True, color=['blue', 'orange', 'purple'], figsize=(14, 8), alpha=0.6)
    plt.title('Occurrences by Event Type', fontsize=16)
    plt.xlabel('Situations', fontsize=14)
    plt.ylabel('Amount', fontsize=14)
    plt.xticks(rotation=45, ha='right', fontsize=12)
    plt.legend(title='Event Type', loc='upper right')
    plt.tight_layout()
    plt.show()

def label_and_file_generator(real=True, simulated=False, drawn=False):
    """This is a generating function that returns tuples for all
    indicated instance sources (`real`, `simulated` and/or
    `hand-drawn`). Each tuple refers to a specific instance and contains
    its label (int) and its full path (Path). All 3W Dataset's instances
    are considered.

    Args:
        real (bool, optional): Indicates whether `real` instances should
            be considered. Defaults to True.
        simulated (bool, optional): Indicates whether `simulated`
            instances should be considered. Defaults to False.
        drawn (bool, optional): Indicates whether `hand-drawn` instances
            should be considered. Defaults to False.

    Yields:
        generator: Tuples for all indicated instance sources. Each tuple
            refers to a specific instance and contains its label (int)
            and its full path (Path).
    """
    for i in Path(PATH_DATASET).iterdir():
        try:
            # Considers only directories
            if i.is_dir():
                label = int(i.stem)
                for fp in i.iterdir():
                    # Considers only Parquet files
                    if fp.suffix == PARQUET_EXTENSION:
                        # Considers only instances from the requested
                        # source
                        if (
                            (simulated and fp.stem.startswith("SIMULATED"))
                            or (drawn and fp.stem.startswith("DRAWN"))
                            or (
                                real
                                and (not fp.stem.startswith("SIMULATED"))
                                and (not fp.stem.startswith("DRAWN"))
                            )
                        ):
                            yield label, fp
        except:
            # Otherwise (e.g. files or directory without instances), do
            # nothing
            pass


def get_all_labels_and_files():
    """Gets lists with tuples related to all real, simulated, or
    hand-drawn instances contained in the 3w Dataset. Each list
    considers instances from a single source. Each tuple refers to a
    specific instance and contains its label (int) and its full path
    (Path).

    Returns:
        tuple: Tuple containing three lists with tuples related to real,
            simulated, and hand-drawn instances, respectively.
    """
    real_instances = list(
        label_and_file_generator(real=True, simulated=False, drawn=False)
    )
    simulated_instances = list(
        label_and_file_generator(real=False, simulated=True, drawn=False)
    )
    drawn_instances = list(
        label_and_file_generator(real=False, simulated=False, drawn=True)
    )

    return real_instances, simulated_instances, drawn_instances


def create_table_of_instances(real_instances, simulated_instances, drawn_instances):
    """Creates a table of instances (pandas.DataFrame) that shows the
    amount of instances that compose the 3W Dataset, by knowledge source
    (real, simulated and hand-drawn instances) and by instance label.

    Args:
        real_instances (list): List with tuples related to all
            real instances contained in the 3w Dataset. Each tuple
            must refer to a specific instance and must contain its label
            (int) and its full path (Path).
        simulated_instances (list): List with tuples related to all
            simulated instances contained in the 3w Dataset. Each tuple
            must refer to a specific instance and must contain its label
            (int) and its full path (Path).
        drawn_instances (list): List with tuples related to all
            hand-drawn instances contained in the 3w Dataset. Each tuple
            must refer to a specific instance and must contain its label
            (int) and its full path (Path).

    Returns:
        pandas.DataFrame: The created table that shows the amount of
            instances that compose the 3W Dataset, by knowledge source
            (real, simulated and hand-drawn instances) and by instance
            label.
    """
    # Gets the label's description of all instances as a list of dicts
    list_instances = (
        [
            {
                "INSTANCE LABEL": str(label) + " - " + LABELS_DESCRIPTIONS[label],
                "SOURCE": "REAL",
            }
            for label, fp in real_instances
        ]
        + [
            {
                "INSTANCE LABEL": str(label) + " - " + LABELS_DESCRIPTIONS[label],
                "SOURCE": "SIMULATED",
            }
            for label, fp in simulated_instances
        ]
        + [
            {
                "INSTANCE LABEL": str(label) + " - " + LABELS_DESCRIPTIONS[label],
                "SOURCE": "HAND-DRAWN",
            }
            for label, fp in drawn_instances
        ]
    )

    # Transforms the list of dicts into a pandas.DataFrame
    df_instances = pd.DataFrame(list_instances)

    # Creates the table of instances with relevant information and
    # desired format
    toi = (
        df_instances.groupby(["INSTANCE LABEL", "SOURCE"])
        .size()
        .reset_index()
        .pivot("SOURCE", "INSTANCE LABEL", 0)
        .fillna(0)
        .astype(int)
        .T
    )
    toi = toi.loc[natsorted(toi.index.values)]
    toi = toi[["REAL", "SIMULATED", "HAND-DRAWN"]]
    toi["TOTAL"] = toi.sum(axis=1)
    toi.loc["TOTAL"] = toi.sum(axis=0)

    return toi


def filter_rare_undesirable_events(toi, threshold, simulated=False, drawn=False):
    """Generates a table of instances (pandas.DataFrame) that shows the
    amount of filtered instances, by knowledge source (real, `simulated`
    and `hand-drawn` instances) and by instance label. This filter keeps
    only real instances, as well as `simulated` and `hand-drawn` if
    indicated, of rare event types. An event type is considered rare if
    the amount of instances labeled as this event relative to the total
    number of instances is less than the indicated `threshold`. In both
    totalizations, `simulated` and `hand-drawn` instances are only
    considered if indicated, but real instances are always taken into
    account.

    Args:
        toi (pandas.DataFrame): Table that shows the amount of instances
            that compose the 3W Dataset, by knowledge source (real,
            `simulated` and `hand-drawn` instances) and by instance
            label. This object is not modified in this function.
        threshold (float): Relative limit that establishes rare event
            types.
        simulated (bool, optional): Indicates whether `simulated`
            instances should be considered. Defaults to False.
        drawn (bool, optional): Indicates whether `hand-drawn` instances
            should be considered. Defaults to False.

    Returns:
        pandas.DataFrame: The table of instances (pandas.DataFrame) that
            shows the amount of filtered instances, by knowledge source
            (real, simulated and hand-drawn instances) and by instance
            label.
    """
    # Simulated and hand-drawn instances are optional, but real
    # instances are always considered
    totals = 0
    if simulated:
        totals += toi["SIMULATED"]
    if drawn:
        totals += toi["HAND-DRAWN"]
    totals += toi["REAL"]

    # Absolute limit
    limit = threshold * totals[-1]

    # Applies the filter in a new pandas.DataFrame
    rue = toi.loc[totals < limit].copy()
    rue.loc["TOTAL"] = rue.sum(axis=0)

    return rue


def load_instance(instance):
    """Loads all data and metadata from a specific `instance`.

    Args:
        instance (tuple): This tuple must refer to a specific `instance`
            and contain its label (int) and its full path (Path).

    Raises:
        Exception: Error if the Parquet file passed as arg cannot be
        read.

    Returns:
        pandas.DataFrame: Its index contains the timestamps loaded from
            the Parquet file. Its columns contain data loaded from the
            other columns of the Parquet file and metadata loaded from
            the argument `instance` (label, well, and id).
    """
    # Loads label metadata from the argument `instance`
    label, fp = instance

    try:
        # Loads well and id metadata from the argument `instance`
        well, id = fp.stem.split("_")

        # Loads data from the Parquet file
        df = pd.read_parquet(fp, engine=PARQUET_ENGINE)
        assert (
            df.columns == COLUMNS_DATA_FILES[1:]
        ).all(), f"invalid columns in the file {fp}: {df.columns.tolist()}"
    except Exception as e:
        raise Exception(f"error reading file {fp}: {e}")

    # Incorporates the loaded metadata
    df["label"] = label
    df["well"] = well
    df["id"] = id

    # Incorporates the loaded data and ordenates the df's columns
    df = df[["label", "well", "id"] + COLUMNS_DATA_FILES[1:]]

    return df


def load_instances(instances):
    """Loads all data and metadata from multiple `instances` in
    parallel.

    Args:
        instances (list): List with tuples related to real, simulated,
            or hand-drawn `instances`. Each tuple must refer to a
            specific instance and must contain its label (int) and its
            full path (Path).

    Returns:
        pandas.DataFrame: Its index contains the timestamps loaded from
            the Parquet files. Its columns contain data loaded from the
            other columns of the Parquet files and the metadata label,
            well, and id).
    """
    # Prepares for multiple parallel loadings
    pool = ThreadPool()
    dfs = []

    try:
        # Calls multiple loadings in parallel
        for df in pool.imap_unordered(load_instance, instances):
            dfs.append(df)
    finally:
        # If the instance cannot be loaded
        pool.terminate()

    # Concatenates dfs and return the result
    return pd.concat(dfs)


def create_and_plot_scatter_map(real_instances):
    """Creates and plots scatter map with all the real instances listed
    in the `real_instances` argument.

    Args:
        real_instances (list): List with tuples related to all
            real instances contained in the 3w Dataset. Each tuple
            must refer to a specific instance and must contain its label
            (int) and its full path (Path).

    Returns:
        tuple: Tuple containing the first and the last year of
            occurrence among all instances, respectively.
    """
    # Loads all instances
    df = load_instances(real_instances)

    # Finds the first and the last year of occurrence among all instances
    df_time = (
        df.reset_index()
        .groupby(["well", "id", "label"])["timestamp"]
        .agg(["min", "max"])
    )

    well_times = defaultdict(list)
    well_classes = defaultdict(list)
    for (well, id, label), (tmin, tmax) in df_time.iterrows():
        well_times[well].append((tmin, (tmax - tmin)))
        well_classes[well].append(label)

    wells = df["well"].unique()
    well_code = {w: i for i, w in enumerate(sorted(wells))}

    # Configures and plots the scatter map
    cmap = plt.get_cmap("Paired")
    my_colors = [cmap(i) for i in [3, 0, 5, 8, 11, 2, 1, 4, 9, 7, 6, 10]]
    my_cmap = mcolors.ListedColormap(my_colors, name="my_cmap")
    plt.register_cmap(name="my_cmap", cmap=my_cmap)
    cmap = plt.get_cmap("my_cmap")
    height = 5
    border = 2
    first_year = np.min(df_time["min"]).year
    last_year = np.max(df_time["max"]).year
    plt.rcParams["axes.labelsize"] = 9
    plt.rcParams["font.size"] = 9
    plt.rcParams["legend.fontsize"] = 9
    fig, ax = plt.subplots(figsize=(9, 9))
    yticks = []
    yticks_labels = []
    for well in well_times.keys():
        times = well_times[well]
        class_names = well_classes[well]
        class_colors = list(map(cmap, class_names))
        well_id = well_code[well]
        yticks.append(well_id * height + height / 2 - border / 2)
        yticks_labels.append(well)
        ax.broken_barh(
            times,
            (well_id * height, height - border),
            facecolors=class_colors,
            edgecolors=class_colors,
        )
    ax.grid(True)
    ax.set_axisbelow(True)
    ax.set_yticks(yticks)
    ax.set_yticklabels(yticks_labels)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    legend_colors = [
        Patch(facecolor=cmap(l), label=str(l) + " - " + d)
        for l, d in LABELS_DESCRIPTIONS.items()
    ]
    ax.legend(
        frameon=False,
        handles=legend_colors,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.12),
        ncol=4,
    )

    return first_year, last_year


def count_properties_instance(instance):
    """Counts properties from a specific `instance`.

    Args:
        instance (tuple): This tuple must refer to a specific `instance`
            and contain its label (int) and its full path (Path).

    Raises:
        Exception: Error if the Parquet file passed as arg cannot be
        read.

    Returns:
        dict: Dict containing the counted properties with the following
            keys: n_vars (number of variables), n_vars_missing (number
            of missing variables), n_vars_frozen (number of frozen
            variables), n_obs (number of observations), and
            n_obs_unlabeled (number of unlabeled observations).
    """
    # Preparation for counting
    _, fp = instance
    p = {"n_vars_missing": 0, "n_vars_frozen": 0}

    try:
        # Read the Parquet file
        df = pd.read_parquet(fp, engine=PARQUET_ENGINE)
    except Exception as e:
        raise Exception(f"error reading file {fp}: {e}")

    # Counts properties
    vars = df.columns[:-1]  # Last column with class is not considered
    p["n_vars"] = len(vars)
    for var in vars:
        if df[var].isnull().all():
            p["n_vars_missing"] += 1
        u_values = df[var].unique()
        if len(u_values) == 1 and not np.isnan(u_values):
            p["n_vars_frozen"] += 1
    p["n_obs"] = len(df)
    p["n_obs_unlabeled"] = df["class"].isnull().sum()

    return p


def count_properties_instances(instances):
    """Counts properties from multiple `instances` in parallel.

    Args:
        instances (list): List with tuples related to real, simulated,
            or hand-drawn `instances`. Each tuple must refer to a
            specific instance and must contain its label (int) and its
            full path (Path).

    Returns:
        dict: Dict containing the counted properties with the following
            keys: n_vars (number of variables), n_vars_missing (number
            of missing variables), n_vars_frozen (number of frozen
            variables), n_obs (number of observations), and
            n_obs_unlabeled (number of unlabeled observations).
    """
    # Prepares for multiple parallel counts
    pool = ThreadPool()
    ps = []

    try:
        # Calls multiple counts in parallel
        for p in pool.imap_unordered(count_properties_instance, instances):
            ps.append(p)
    finally:
        # If the instance cannot be loaded
        pool.terminate()

    # Sum ps and return the result
    return dict(pd.DataFrame(ps).sum())


def calc_stats_instances(real_instances, simulated_instances, drawn_instances):
    """Calculates the 3W Dataset's fundamental aspects related to
    inherent difficulties of actual data. Three statistics are
    calculated: Missing Variables, Frozen Variables, and Unlabeled
    Observations. All instances, regardless of their source, influence
    these statistics.

    Args:
        real_instances (list): List with tuples related to all
            real instances contained in the 3w Dataset. Each tuple
            must refer to a specific instance and must contain its label
            (int) and its full path (Path).
        simulated_instances (list): List with tuples related to all
            simulated instances contained in the 3w Dataset. Each tuple
            must refer to a specific instance and must contain its label
            (int) and its full path (Path).
        drawn_instances (list): List with tuples related to all
            hand-drawn instances contained in the 3w Dataset. Each tuple
            must refer to a specific instance and must contain its label
            (int) and its full path (Path).

    Returns:
        pandas.DataFrame: Its index contains the statistic's names. Its
            columns contain statistics themselves (Amount and
            Percentage)
    """
    # Counts properties from all indicated instances
    p = count_properties_instances(
        real_instances + simulated_instances + drawn_instances
    )

    # Extract properties
    n_vars = p["n_vars"]
    n_vars_missing = p["n_vars_missing"]
    n_vars_frozen = p["n_vars_frozen"]
    n_obs = p["n_obs"]
    n_obs_unlabeled = p["n_obs_unlabeled"]

    # Calculates the statistics
    stats = {
        "Missing Variables": [
            n_vars_missing,
            f"{100*n_vars_missing/n_vars:.2f}% of {n_vars}",
        ],
        "Frozen Variables": [
            n_vars_frozen,
            f"{100*n_vars_frozen/n_vars:.2f}% of {n_vars}",
        ],
        "Unlabeled Observations": [
            n_obs_unlabeled,
            f"{100*n_obs_unlabeled/n_obs:.2f}% of {n_obs}",
        ],
    }

    return pd.DataFrame.from_dict(
        stats, orient="index", columns=["Amount", "Percentage"]
    )


def resample(data, n, class_number):
    """Downsampling for instances.

    Args:
        data (string): Instance path
        n (integer): Factor to downsampling the instance.
        class_number (integer): integer that represents the event class

    Returns:
        pandas.DataFrame: Downsamplig instance DataFrame
    """
    # Timestamp is expected to be a column
    data.reset_index(inplace=True)
    # Group Timestamp and get last value
    resampleTimestamp = data.timestamp.groupby(data.index // n).max()
    # Replace transient label from 100 to 0.5
    data["class"] = data["class"].astype(float)
    tempClassLabel = data["class"].replace(class_number + 100, 0.5)
    # Get the max value from the group Class column
    resampleClass = tempClassLabel.groupby(tempClassLabel.index // n).max()
    # Back with transient label value
    resampleClass.replace(0.5, class_number + 100, inplace=True)
    # Non overlap group and get the average value from the data
    dfResample = data.groupby(data.index // n).mean(numeric_only=True)
    # Drop class column
    dfResample.drop(["class"], axis=1, inplace=True)
    # Insert resampled class label values
    dfResample["class"] = resampleClass
    # Insert resampled timestamp
    dfResample.index = resampleTimestamp

    return dfResample


def plot_instance(class_number, instance_index, resample_factor):
    """Plot one especific event class and instance. By default the
    instance is downsampling (n=100) and Z-score Scaler. In order to
    help the visualization transient labels was changed to '0.5'.

    Args:
        class_number (integer): integer that represents the event class
        instance_index (integer): input the instance file index
    """
    instances_path = os.path.join(
        PATH_DATASET, str(class_number), "*" + PARQUET_EXTENSION
    )
    instances_path_list = glob.glob(instances_path)
    if instance_index >= len(instances_path_list):
        print(
            f"instance index {instance_index} out of range - Insert a valid index between 0 and {len(instances_path_list)-1}"
        )
    else:
        df_instance = pd.read_parquet(
            instances_path_list[instance_index], engine=PARQUET_ENGINE
        )
        df_instance_resampled = resample(df_instance, resample_factor, class_number)
        df_drop_resampled = df_instance_resampled.drop(["state", "class"], axis=1)
        df_drop_resampled.interpolate(
            method="linear", limit_direction="both", axis=0, inplace=True
        )
        df_drop_resampled.fillna(
            0,
            inplace=True,
        )
        scaler_resampled = TimeSeriesScalerMeanVariance().fit_transform(
            df_drop_resampled
        )

        df_scaler_resampled = pd.DataFrame(
            scaler_resampled.squeeze(),
            index=df_drop_resampled.index,
            columns=df_drop_resampled.columns,
        )
        df_instance_resampled["class"] = df_instance_resampled["class"].replace(
            100 + int(class_number), 0.5
        )
        df_instance_resampled["class"] = df_instance_resampled["class"].replace(
            int(class_number), 1
        )

        colors_traces = [
            "#008080",
            "#3498DB",
            "#E74C3C",
            "#884EA0",
            "#D4AC0D",
            "#AF601A",
            "#D35400",
            "#839192",
            "#2E4053",
        ]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_scaler_resampled[VARS[0]],
                mode="lines+markers",
                marker_symbol="circle",
                marker_size=3,
                name=VARS[0],
                yaxis="y1",
                line_color=colors_traces[0],
            )
        ),
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_scaler_resampled[VARS[1]],
                mode="lines+markers",
                marker_symbol="diamond",
                marker_size=3,
                name=VARS[1],
                yaxis="y2",
                line_color=colors_traces[1],
            )
        ),
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_scaler_resampled[VARS[2]],
                mode="lines+markers",
                marker_symbol="x",
                marker_size=3,
                name=VARS[2],
                yaxis="y3",
                line_color=colors_traces[2],
            )
        ),
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_scaler_resampled[VARS[3]],
                mode="lines+markers",
                marker_symbol="star",
                marker_size=3,
                name=VARS[3],
                yaxis="y4",
                line_color=colors_traces[3],
            )
        ),
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_scaler_resampled[VARS[4]],
                mode="lines+markers",
                marker_symbol="triangle-up",
                marker_size=3,
                name=VARS[4],
                yaxis="y5",
                line_color=colors_traces[4],
            )
        ),
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_scaler_resampled[VARS[5]],
                mode="lines",
                name=VARS[5],
                yaxis="y6",
                line_color=colors_traces[5],
            )
        ),
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_scaler_resampled[VARS[6]],
                mode="lines",
                name=VARS[6],
                yaxis="y7",
                line_color=colors_traces[6],
            )
        ),
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_scaler_resampled[VARS[7]],
                mode="lines",
                name=VARS[7],
                yaxis="y8",
                line_color=colors_traces[7],
            )
        ),
        fig.add_trace(
            go.Scatter(
                x=df_instance_resampled.index,
                y=df_instance_resampled["class"],
                mode="markers",
                name="Label",
                yaxis="y9",
                line_color=colors_traces[8],
            )
        ),
        fileName = instances_path_list[instance_index].split(os.sep)
        fig.update_layout(
            title=EVENT_NAMES[class_number] + " - " + fileName[-1],
            xaxis_title="Time(s)",
            yaxis_title="z-score",
            font=dict(size=12),
            yaxis1=dict(
                tickfont=dict(color=colors_traces[0]),
                position=0,
                tickformat=".2f",
                showticklabels=False,
            ),
            yaxis2=dict(
                tickfont=dict(color=colors_traces[1]),
                overlaying="y",
                side="left",
                position=0.05,
                tickformat=".2f",
                showticklabels=False,
            ),
            yaxis3=dict(
                tickfont=dict(color=colors_traces[2]),
                overlaying="y",
                side="left",
                position=0.10,
                tickformat=".2f",
                showticklabels=False,
            ),
            yaxis4=dict(
                tickfont=dict(color=colors_traces[3]),
                overlaying="y",
                side="left",
                position=0.15,
                tickformat=".2f",
                showticklabels=False,
            ),
            yaxis5=dict(
                tickfont=dict(color=colors_traces[4]),
                overlaying="y",
                side="left",
                position=0.2,
                tickformat=".2f",
                showticklabels=False,
            ),
            yaxis6=dict(
                tickfont=dict(color=colors_traces[5]),
                overlaying="y",
                side="left",
                position=0.25,
                tickformat=".2f",
                showticklabels=False,
            ),
            yaxis7=dict(
                tickfont=dict(color=colors_traces[6]),
                overlaying="y",
                side="left",
                position=0.3,
                tickformat=".2f",
                showticklabels=False,
            ),
            yaxis8=dict(
                tickfont=dict(color=colors_traces[7]),
                overlaying="y",
                side="left",
                position=0.35,
                tickformat=".2f",
                showticklabels=False,
            ),
            yaxis9=dict(
                tickfont=dict(color=colors_traces[8]),
                anchor="x",
                overlaying="y",
                side="left",
            ),
        )
        fig.show()
