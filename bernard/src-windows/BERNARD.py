import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import datetime
#import subprocess
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=pd.errors.SettingWithCopyWarning)
from bernard_library import merge_dataframes
from pyCombat import combat
#from workflows import workflow_for_corrected
from bernard_library import delete_tmp_files
from bernard_library import table_for_dimensionality_reduction_variables
from bernard_library import table_for_dimensionality_reduction
from bernard_library import PCA
from bernard_library import MDS
from bernard_library import TSNE
from bernard_library import NMDS
from bernard_library import PCoA
from bernard_library import dissimilarity_heatmap
from bernard_library import graph_connectivity_plot
#from bernard_library import UMAP
from workflows import workflow
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows
import json
import re
from bernard_library import corrected_data_analysis
from bernard_library import run_R
import methods as bmethods
import scoring as bscoring
from bernard_library import cleaning
from bernard_library import pie_charts
from bernard_library import phenotype_pie_per_batch
import time
start_time_full = time.time()

import sys
import bml.params as params
import bml.files as bfiles

print("\n\nBernard V1.0, date 2025_04_24\n\n")

import settings as bsettings
import validation as bvalidation

USAGE = """
BERNARD - Batch Effect Removal and Noise-Reducing Algorithm for Raw Datasets

    python3 BERNARD.py <settings file> [<work folder>]

        Run a complete analysis. Everything BERNARD can be told is written in the settings
        file, in lines of the form   name = value

    python3 BERNARD.py --check <settings file> [<work folder>]

        Check the settings file and the input data and report every problem found in them,
        without calculating anything.

    python3 BERNARD.py --template > bernard_cfg.txt

        Write a settings file with every setting explained and set to its default.

    python3 BERNARD.py --help

        Print this text.
"""

error_log_folder = [os.getcwd()]


def report_unexpected_error(kind, value, trace):
    import traceback

    log_path = os.path.join(error_log_folder[0], 'bernard-error.log')

    try:
        with open(log_path, 'w') as log_file:
            traceback.print_exception(kind, value, trace, file=log_file)
    except Exception:
        log_path = None

    print('')
    print('=' * 99)
    print('BERNARD stopped because of an unexpected error.')
    print('=' * 99)
    print('')
    print('    ' + kind.__name__ + ': ' + str(value))
    print('')
    if log_path:
        print('    The full technical detail was written to')
        print('        ' + log_path)
    print('')
    print('    If the input data may be the cause, running')
    print('        python3 BERNARD.py --check <settings file>')
    print('    checks the settings and the data and usually names the problem directly.')
    print('')

    sys.exit(1)


sys.excepthook = report_unexpected_error

arguments = sys.argv[1:]
check_only = False
positional = []

for argument in arguments:
    if argument in ('--help', '-h', 'help'):
        print(USAGE)
        sys.exit(0)

    if argument in ('--template', '-t'):
        print(bsettings.template())
        sys.exit(0)

    if argument in ('--check', '-c', '--dry-run'):
        check_only = True
        continue

    if argument.startswith('-'):
        print('\nUnknown option: ' + argument)
        print(USAGE)
        sys.exit(-1)

    positional.append(argument)

if len(positional) < 1 or len(positional) > 2:
    print('\nError: expected a settings file' + (' and nothing else' if len(positional) == 0
                                                 else ', and at most a work folder after it')
          + ', but got ' + str(len(positional)) + ' argument(s).')
    print(USAGE)
    sys.exit(-1)

cfg_file_name = positional[0]

if len(positional) == 2:
    work_dir = positional[1].rstrip('/')
else:
    work_dir = os.path.dirname(os.path.abspath(cfg_file_name))

error_log_folder[0] = work_dir

settings_values, settings_problems = bsettings.read(cfg_file_name)

if bvalidation.has_errors(settings_problems):
    bvalidation.report(settings_problems, 'The settings file ' + cfg_file_name)
    print('Nothing was calculated. Correct the settings file and run BERNARD again.\n')
    sys.exit(2)

pending_problems = list(settings_problems)


def make_abs_path(in_path: str):
    """Convert relative path that begins with ~ (home dir) or . (current dir) into an absolute one."""
    if in_path is None:
        return None

    if not isinstance(in_path, str):
        return None

    if len(in_path) == 0:
        return None

    in_path = in_path.rstrip('/')

    if len(in_path) == 0:
        return None

    if in_path[0] == '~':
        return os.path.expanduser(in_path)

    if in_path[0] == '.':
        return work_dir + in_path[1:]

    if len(in_path) >= 3 and in_path[1] == ':' and in_path[0].isalpha() \
            and in_path[2] in ('/', '\\'):
        return in_path

    if in_path[0] != '/':
        return work_dir + '/' + in_path

    return in_path


bernard_input = settings_values.get('bernard_input')

if bernard_input is None:
    print("\nError: bernard_input not specified in config file. Aborting.\n")

    sys.exit(-1)

bernard_input = make_abs_path(bernard_input)
bernard_input_split = bfiles.split(bernard_input)

import bml.zip_util # also needed at the end, so importing unconditionally

if bernard_input_split['ext'].lower() == '.zip':
    bml.zip_util.extract_zip_ignore_single_root(
        bernard_input,
        f"{bernard_input_split['dir']}/raw-data")

    bernard_folder = bernard_input_split['dir']
else:
    bernard_folder = bernard_input


import glb
glb.bernard_folder = bernard_folder

raw_data_folder = bernard_folder + "/raw-data"
glb.raw_data_folder = raw_data_folder


select_thresholdSamples   = settings_values['select_thresholdSamples']
select_thresholdFeatures  = settings_values['select_thresholdFeatures']
delete_tmp_corrected_data = settings_values['delete_tmp_corrected_data']
retained_variability      = settings_values['diagnosis_variability_retention']
lower_limit_variability   = settings_values['diagnosis_variability_lower_limit']
variability_step          = settings_values['variability_threshold_step']

processing = f"Removing features with more than {select_thresholdFeatures*100} percentage of zero values. Removing samples with more than {select_thresholdSamples*100 } percentage of zero values."

glb.run_permdisp              = settings_values['run_permdisp']
glb.permdisp_permutations     = settings_values['permdisp_permutations']
glb.permdisp_test             = settings_values['permdisp_test']
glb.run_neighbourhood_metrics = settings_values['run_neighbourhood_metrics']
glb.neighbourhood_k           = settings_values['neighbourhood_k']
glb.evaluation_space          = settings_values['evaluation_space']
glb.outlier_contamination     = settings_values['outlier_contamination']
glb.run_auroc                 = settings_values['run_auroc']
glb.run_stability             = settings_values['run_stability']
glb.stability_resamples       = settings_values['stability_resamples']
glb.stability_fraction        = settings_values['stability_fraction']

glb.random_seed             = settings_values['random_seed']
glb.permanova_permutations  = settings_values['permanova_permutations']
glb.significance_alpha      = settings_values['significance_alpha']
glb.kbet_alpha              = settings_values['kbet_alpha']
glb.auroc_trees             = settings_values['auroc_trees']
glb.auroc_folds             = settings_values['auroc_folds']
glb.pvca_variance_threshold = settings_values['pvca_variance_threshold']
glb.pvca_max_components     = settings_values['pvca_max_components']
glb.tsne_perplexity         = settings_values['tsne_perplexity']
glb.figure_dpi              = settings_values['figure_dpi']

selected_methods = bmethods.select_methods(settings_values.get('correction_methods'),
                                           settings_values.get('exclude_correction_methods'))
print("Batch effect correction methods to run (" + str(len(selected_methods)) + " of "
      + str(len(bmethods.ALL_METHODS)) + "): "
      + ", ".join(method.label for method in selected_methods))

import runner as brunner

max_parallel_methods = settings_values['max_parallel_methods']
if not max_parallel_methods:
    max_parallel_methods = brunner.default_worker_count(len(selected_methods))
method_timeout_seconds = int(settings_values['method_timeout_minutes']) * 60

script_folder = os.path.dirname(os.path.abspath(__file__))

data_problems, columns, dataset_files = bvalidation.check_input(
    bernard_folder, settings_values, selected_methods, script_folder)

pending_problems.extend(data_problems)

if pending_problems:
    bvalidation.report(pending_problems, 'This run')

if bvalidation.has_errors(pending_problems):
    print('Nothing was calculated. Correct the problems above and run BERNARD again.\n')
    sys.exit(2)

study_name         = columns['study_name']
factor_of_interest = columns['factor_of_interest']
sample_id_column   = columns['sample_id_column']

dataset_order = {os.path.splitext(name)[0]: position
                 for position, name in enumerate(dataset_files)}


def dataset_rank(name):
    if not isinstance(name, str):
        return len(dataset_order)

    stem = os.path.splitext(os.path.basename(name))[0]

    if stem.startswith('clean-'):
        stem = stem[len('clean-'):]

    return dataset_order.get(stem, len(dataset_order))


def smallest_first(folder, names):
    def size(name):
        try:
            return os.path.getsize(os.path.join(folder, name))
        except OSError:
            return float('inf')

    return sorted(names, key=lambda name: (size(name), name))

write_failure = bvalidation.write_columns_definition(raw_data_folder, columns, settings_values)
if write_failure:
    print('\nWARNING: ' + write_failure)
    print('The R correction methods read those files, so they may use different column names.\n')

metadata = list(columns['covariates'])
covariates = [study_name, factor_of_interest] + metadata
print("Metadata:", metadata)
print("Metadata with covariates:", covariates)

if check_only:
    print('')
    print('--check was given, so nothing was calculated.')
    print('The settings file and the input data hold no errors: this run would go ahead.')
    print('    datasets          : ' + ', '.join(dataset_files))
    print('    batch column      : ' + str(study_name))
    print('    factor of interest: ' + str(factor_of_interest))
    print('    sample ID column  : ' + str(sample_id_column))
    print('    covariates        : ' + (', '.join(metadata) if metadata else '(none)'))
    print('    methods           : ' + ', '.join(m.label for m in selected_methods))
    print('    at a time         : ' + str(max_parallel_methods))
    print('')
    sys.exit(0)

outputs = bernard_folder + "/outputs"
output_path = f"{outputs}"
corrected_outputs = outputs + "/corrected"
report_dir = outputs + "/report"
log_dir = outputs + "/logs"

if not check_only:
    for folder in (outputs, corrected_outputs, outputs + "/cleaned", report_dir, log_dir):
        bfiles.recreate_dir(folder)

        if not os.path.exists(folder):
            sys.exit(f"ERROR: The path '{folder}' does not exist.")

        if not os.path.isdir(folder):
            sys.exit(f"ERROR: The path '{folder}' exists but is not a directory.")

    error_log_folder[0] = outputs

    tag_files = bfiles.list_in_dir(raw_data_folder, 'tag.txt', full_path = True)
    if len(tag_files) == 1:
        bfiles.copy_to_dir(tag_files[0], outputs)


# Set the date to identify outputs of anlysis
full_date = datetime.datetime.now()
date = str(full_date)
date = date[:-7].replace(" ", "-").replace(":", "")

calculations = pd.DataFrame() #setting up empty dataframe where all calculations will be stored

input_folder = f"{raw_data_folder}" # raw data before batch effect correction
output_path = f"{outputs}" # processed data will be stored here

data_cleaning_time = None
data_cleaning_time_with_statistics = None
cleaned_datasets = []
failed_datasets = []

import runtimes as bruntimes
dataset_timings = []

for data_file in dataset_files:
    filepath = os.path.join(raw_data_folder, data_file)

    start_time = time.time()

    try:
        clean_df, data_file, raw_dict, data_cleaning_time = cleaning(
            data_file, #current raw data file
            filepath, #path to current raw data file
            sample_id_column,
            processing, #processing message
            workflow=workflow, #workflow for processing and calculations before batch effect correction
            output_path=output_path, #storing processed data here
            thresholdSamples=select_thresholdSamples, #defined in the settings file
            thresholdFeatures=select_thresholdFeatures, #defined in the settings file
            study_name=study_name,
            factor_of_interest=factor_of_interest
            )
    except SystemExit as stopped:
        failed_datasets.append((data_file, str(stopped)))
        print(f"\nWARNING: {data_file} could not be prepared: {stopped}")
        print("This dataset is left out of the run; the others are processed as usual.\n")
        continue
    except Exception as failure:
        import traceback
        failed_datasets.append((data_file, str(failure)))
        print(f"\nWARNING: {data_file} could not be prepared: {failure}")
        print("    " + traceback.format_exc().splitlines()[-1])
        print("This dataset is left out of the run; the others are processed as usual.\n")
        continue

    end_time = time.time()
    data_cleaning_time_with_statistics = end_time - start_time
    cleaned_datasets.append(data_file)

    dataset_timings.append({
        'name':                     data_file,
        'size_mb':                  bruntimes.file_size_mb(filepath),
        'samples':                  raw_dict.get('initial number of samples'),
        'features':                 raw_dict.get('initial number of features'),
        'samples_after':            raw_dict.get('new number of samples'),
        'features_after':           raw_dict.get('new number of features'),
        'cleaning':                 data_cleaning_time,
        'cleaning_with_statistics': data_cleaning_time_with_statistics,
    })

    # Converting raw-dict to dataframe.
    calculations_to_add = pd.DataFrame([raw_dict]).set_index("datasetName")
    calculations_to_add.to_excel(f"{output_path}/tmp-calculations-to-add-{data_file}.xlsx")
    calculations = merge_dataframes(calculations, calculations_to_add)

if not cleaned_datasets:
    print("")
    print("=" * 99)
    print("None of the datasets could be prepared, so there is nothing to correct.")
    print("=" * 99)
    for name, reason in failed_datasets:
        print("    " + name + ": " + reason)
    print("")
    sys.exit(3)

if failed_datasets:
    print("\n" + str(len(failed_datasets)) + " dataset(s) were left out of this run:")
    for name, reason in failed_datasets:
        print("    " + name + ": " + reason)

calculations.to_excel(f"{output_path}/tmp-calculations-raw.xlsx")

# Load existing calculations
full_calculation = pd.read_excel(f"{output_path}/tmp-calculations-raw.xlsx")
full_calculation.drop(list(full_calculation.filter(regex='Unnamed:')), axis=1, inplace=True)

calculation_holder = [full_calculation]


def measure_method(correction_method):
    calculation_holder[0] = corrected_data_analysis(
        raw_data_folder, corrected_outputs, sample_id_column, calculation_holder[0],
        suffix=correction_method.suffix, method=correction_method.method,
        study_name=study_name, factor_of_interest=factor_of_interest)


start_time_correction = time.time()

method_outcome_records = brunner.run_methods(
    selected_methods,
    script_folder=script_folder,
    bernard_folder=bernard_folder,
    corrected_outputs=corrected_outputs,
    log_folder=log_dir,
    max_workers=max_parallel_methods,
    timeout_seconds=method_timeout_seconds,
    analyse=measure_method,
    analyse_while_running=settings_values['parallel_analysis'],
    stop_on_failure=settings_values['stop_on_method_failure'])

full_calculation = calculation_holder[0]

correction_and_scoring_time = time.time() - start_time_correction

method_runtimes = [(outcome.method.label, outcome.runtime) for outcome in method_outcome_records]
method_outcomes = [{'method': outcome.method.label,
                    'status': outcome.status if outcome.status == 'completed'
                              else outcome.status.upper() + ' (' + str(outcome.message) + ')',
                    'output_files': len(brunner.produced_files(corrected_outputs, outcome.method)),
                    'runtime_seconds': round(outcome.runtime, 2)}
                   for outcome in method_outcome_records]

method_order = {method.method: position for position, method in enumerate(bmethods.ALL_METHODS)}
if 'method' in full_calculation.columns:
    full_calculation['__order'] = full_calculation['method'].map(
        lambda name: method_order.get(name, -1) if isinstance(name, str) else -1)
    full_calculation['__dataset'] = full_calculation['datasetName'].map(dataset_rank)
    full_calculation = full_calculation.sort_values(
        ['__dataset', 'datasetName', '__order'], kind='stable').drop(
        columns=['__dataset', '__order']).reset_index(drop=True)

successful_methods = [outcome for outcome in method_outcome_records
                      if outcome.status == 'completed']

print('')
print(str(len(successful_methods)) + ' of ' + str(len(selected_methods))
      + ' correction method(s) produced a result.')

if not successful_methods:
    print('')
    print('=' * 99)
    print('Not one correction method produced a result, so there is nothing to compare.')
    print('=' * 99)
    print('')
    print('The output of each method was written to')
    print('    ' + log_dir)
    print('and usually names the cause: most often an R package that is not installed on this')
    print('machine. Running')
    print('    Rscript requirements/RPackages.R')
    print('installs them. To run without R at all, put this in the settings file:')
    print('    correction_methods = pyCombat')
    print('')
    sys.exit(3)

# Temporary excel file is stored.
# The excel contains PERMANOVA and PLS results for all datasets before and after batch effect correction with each method.
full_calculation.to_excel(f"{output_path}/tmp-after-correction.xlsx")

start_time_selection = time.time()

full_calculation["datasetName"] = full_calculation["datasetName"].str.replace("clean-", "", regex=False)
full_calculation["datasetName"] = full_calculation["datasetName"].str.replace("csv", "", regex=False)
full_calculation["datasetName"] = full_calculation["datasetName"].str.replace("tsv", "", regex=False)
full_calculation["datasetName"] = full_calculation["datasetName"].str.replace(r'\.$', '', regex=True)
#full_calculation = full_calculation.drop_duplicates(subset=["datasetName", "method"], keep="first")

# fill missing values within each dataset group using values from the first non-empty row of that group (the first row has calculations before dataset was batch corrected).
for dataset in full_calculation['datasetName'].unique(): #goes through each unique dataset name
    mask = full_calculation['datasetName'] == dataset #True and False values, if value is True, row is linked to current dataset
    calculations = full_calculation.loc[mask].dropna(how='all') #filters the DataFrame to include only rows belonging to the current

    if not calculations.empty: #at least one non-empty row needs to be in filtered dataframe
        if 'method' in calculations.columns:
            baseline = calculations[calculations['method'].isna()
                                    | (calculations['method'].astype(str) == 'uncorrected')]
        else:
            baseline = calculations.iloc[0:0]
        if baseline.empty:
            print(f"WARNING: no uncorrected baseline row found for {dataset}. The raw measurements "
                  f"cannot be copied to the method rows, so the retention percentages will be empty.")
            baseline = calculations.iloc[0:1]
        calculations_dict = baseline.iloc[0].to_dict()
        # Fill only NaN values
        for col, value in calculations_dict.items():
            if col in full_calculation.columns and col != 'datasetName':
                if value is None or (not isinstance(value, str) and pd.isna(value)):
                    continue
                full_calculation.loc[mask, col] = full_calculation.loc[mask, col].fillna(value) 
                # values from first row are copy-pasted to all other rows in the same column

full_calculation.to_excel(f"{output_path}/tmp-calculations.xlsx")
full_calculation = pd.read_excel(f"{output_path}/tmp-calculations.xlsx")
numeric_cols = [f"permanova-{study_name}-R2", 
                f"permanova-{factor_of_interest}-R2", 
                f"permanova-{study_name}-R2-corrected", 
                f"permanova-{factor_of_interest}-R2-corrected"]

# Convert relevant columns to numeric, forcing errors to NaN if necessary
for col in numeric_cols:
    full_calculation[col] = pd.to_numeric(full_calculation[col], 
                                          errors="coerce")

full_calculation["bioproject_variability_retention"] = (full_calculation[f"permanova-{study_name}-R2-corrected"] / full_calculation[f"permanova-{study_name}-R2"]) * 100
full_calculation["diagnosis_variability_retention"] = (full_calculation[f"permanova-{factor_of_interest}-R2-corrected"] / full_calculation[f"permanova-{factor_of_interest}-R2"]) * 100 # MIN 50%

full_calculation, ranking_orderings = bscoring.score_methods(
    full_calculation, study_name, factor_of_interest,
    alpha=settings_values['significance_alpha'])

bscoring.report_decision(full_calculation, study_name, factor_of_interest,
                         settings_values['significance_alpha'])

best_methods = full_calculation[full_calculation[bscoring.BEST_COLUMN] == "Best performance"]

gate_skipped = bscoring.gate_skipped_datasets(full_calculation)
for dataset in gate_skipped:
    winner = best_methods[best_methods["datasetName"] == dataset]
    name = str(winner["method"].iloc[0]) if len(winner) else "none"
    reason = str(winner[bscoring.REASON_COLUMN].iloc[0]) if len(winner) else "it did not pass step 1"
    print(f"\nWARNING: no method passed the first step of the decision for {dataset}. Step 1 was "
          f"skipped and all methods were ranked on the 21 measures instead; the best selected "
          f"method is {name}, which did not pass step 1 either: {reason}.")

if best_methods.empty:
    print("\nWARNING: no method could be ranked for any dataset. The results are still "
          "written out, but no method is marked as best.")

# Save final results
full_calculation.to_excel(f"{output_path}/tmp-calculations-suitability.xlsx")


if glb.run_auroc:
    from bernard_library import roc_plot
    for dataset, method in zip(best_methods["datasetName"], best_methods["method"]):
        roc_plot(dataset, method, outputs, date)

full_calculation.drop(list(full_calculation.filter(regex='Unnamed:')), axis=1, inplace=True)
full_calculation["method"].fillna("uncorrected", inplace = True)

# Highlight "Best performance" rows
# Create a new Excel workbook and sheet
wb = Workbook()
ws = wb.active
ws.title = "calculations"
# Write DataFrame to Excel
for r in dataframe_to_rows(full_calculation, index=False, header=True):
    ws.append(r)
# Find the correct column index for "Best performance"
best_perf_col_index = [cell.value for cell in ws[1]].index("Best performance")
# Define highlight color
highlight = PatternFill(start_color="FFCC99", end_color="FFCC99", fill_type="solid")
# Apply highlighting to rows with "Best performance"
for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
    if str(row[best_perf_col_index].value).strip().lower() == "best performance":
        for cell in row:
            cell.fill = highlight  # Apply color
lists_sheet = wb.create_sheet("ranking-lists")
for r in dataframe_to_rows(ranking_orderings, index=False, header=True):
    lists_sheet.append(r)

# Save the Excel file
wb.save(f"{output_path}/final-calculations{date}.xlsx")
print("Dataframe is saved in final-calculations.xlsx file.")

stability_results = []
if glb.run_stability:
    import stability as bstability
    from bernard_library import stability_plot
    glb.stability_measures = settings_values['stability_measures']
    glb.stability_permanova_permutations = settings_values['stability_permanova_permutations']
    glb.stability_blas_threads = settings_values['stability_blas_threads']
    for dataset in full_calculation['datasetName'].dropna().unique():
        try:
            result = bstability.analyse(str(dataset), raw_data_folder, corrected_outputs,
                                        sample_id_column, study_name, factor_of_interest,
                                        outputs + "/cleaned")
        except Exception as e:
            print(f"ERROR: stability analysis failed for {dataset}: {e}")
            continue
        if not result:
            continue
        stability_results.append(result)
        stability_plot(result, outputs, f"{dataset}-stability-{date}")
        pd.DataFrame(result['methods']).to_excel(
            f"{output_path}/stability-{dataset}-{date}.xlsx", index=False)
        top = result['methods'][0]
        print(f"\nStability for {dataset}: {top['method']} chosen in {top['wins']} of "
              f"{result['decided']} subsamples ({100 * (top['selection-frequency'] or 0):.0f}%)"
              + (f", Kendall's W {result['kendalls-w']:.2f}" if result['kendalls-w'] is not None else ""))
        if (top['selection-frequency'] or 0) < 0.5:
            print(f"WARNING: no method wins a majority of the subsamples for {dataset}. "
                  f"The single best method should be reported as one of several defensible choices.")
        if result['gate-skipped-resamples']:
            print(f"NOTE: in {result['gate-skipped-resamples']} of {result['decided']} subsamples "
                  f"no method passed step 1, so the winner there is the best of a field in which "
                  f"none succeeded.")

# Remove tmp from best batch effect corrected file (tmp will remain in all other corrected files)
suffix_of_method = {method.method: method.suffix for method in bmethods.ALL_METHODS}
for index, row in full_calculation.iterrows():
    # Check if the row has 'Best performance' in the Best performance column
    if row['Best performance'] == 'Best performance':
        dataset_name = row['datasetName'].split(".", 1)[0]
        method = row['method']
        # It gives you a dataset name and method with best performance for this dataset
        # Based on those two information best corrected datasets loses tmp substring.
        # Construct the search pattern for files containing both dataset name and method
        suffix = suffix_of_method.get(method, f"_{method}-tmp")
        renamed_files = []
        for filename in os.listdir(corrected_outputs):
            if f"{dataset_name}_" in filename and suffix in filename:
                old_filename = os.path.join(corrected_outputs, filename)
                new_filename = os.path.join(corrected_outputs, filename.replace('tmp', f'{date}'))  #removes 'tmp' substring
                os.rename(old_filename, new_filename) #renames the file
                renamed_files.append(filename)
                print(f'Renamed: {filename} -> {os.path.basename(new_filename)}')
        if not renamed_files:
            print(f"WARNING: no corrected file matching '{suffix}' was found for the best method "
                  f"({method}) of {dataset_name}. The corrected data of this dataset cannot be "
                  f"marked as the winner's, so the report will hold the raw pictures only.")

# Cleaning filenames...
delete_tmp_files(output_path)
if gate_skipped or best_methods.empty:
    print("Corrected datasets in outputs/corrected are kept: no method passed the first step of "
          "the decision process, so the corrected data of every method is left for inspection.")
elif delete_tmp_corrected_data == True: #defined in bernard_cfg.txt, default is True
    delete_tmp_files(corrected_outputs) #deletes all files in directory that contains tmp
else:
    from bernard_library import remove_tmp_from_filenames
    remove_tmp_from_filenames(corrected_outputs) #if delete_tmp_corrected_data is set to False, tmp will be removed from all files in directory

files = os.listdir(corrected_outputs)

for filename in files:
        current_path = os.path.join(corrected_outputs, filename)
        if not os.path.isfile(current_path):
            continue
        if 'clean-' in filename:
            new_name = filename.replace('clean-', '')
            new_path = os.path.join(corrected_outputs, new_name)
            os.rename(current_path, new_path)
            #print(f"Renamed: {filename} -> {new_name}")

selection_time = time.time() - start_time_selection

start_time_report = time.time()

for dirpath, dirnames, filenames in os.walk(input_folder): #goes through folder with raw (uncorrected) datasets
    for file in smallest_first(dirpath, filenames):
        if file.startswith("."):  # Skip hidden files like
            continue #skip the rest of this loop iteration and move to the next file
        if "metadata" not in file and "config" not in file and "covariates" not in file:
            file_path = os.path.join(dirpath, file)
            #print("File name: ", file_path)
            if file_path.endswith(".csv"):
                raw_data = pd.read_csv(file_path, low_memory=False) #opens a file
            if file_path.endswith(".tsv"):
                raw_data = pd.read_csv(file_path, sep="\t", low_memory=False) #opens a file
            # Pie chart - raw data
            # Plots a proportion of samples belonging to each batch group and diagnosis/treatment group
            pie_charts(raw_data, output=outputs, title=f"pie-chart-raw-{file}-{date}")
            phenotype_pie_per_batch(raw_data, output=outputs,
                                    title=f"pie-chart-balance-raw-{file}-{date}")
            # Dimensionality reduction - raw data
            # It reduces dimensionality to two components using following methods:
            # - Principal component analysis
            # - Multidimensional scaling
            # - t-distributed stochastic neighbor embedding
            # Visualise the output of a dimensional reduction technique on a 2D scatter plot
            try:
                raw_data = raw_data.set_index("Unnamed: 0")
            except: raw_data = raw_data.set_index(sample_id_column)
            variables = table_for_dimensionality_reduction_variables(raw_data) #returns only numeric columns with standardized values
            target_bioproject = table_for_dimensionality_reduction(raw_data, study_name) #dataframe with batch column only
            target_diagnosis = table_for_dimensionality_reduction(raw_data, factor_of_interest) #dataframe with factor of interest column only
            PCA(variables, 
                target_bioproject, 
                target_diagnosis, 
                title="PCA-raw-data", 
                file_name=f"raw-{file}-{date}", 
                features_list=[study_name, factor_of_interest], #feature list has two values: study_name and factor_of_interest
                output=outputs)
            MDS(variables, 
                target_bioproject, 
                target_diagnosis, 
                title="MDS-raw-data", 
                file_name=f"raw-{file}-{date}", 
                features_list=[study_name, factor_of_interest], #feature list has two values: study_name and factor_of_interest
                output=outputs)
            TSNE(variables, 
                target_bioproject, 
                target_diagnosis, 
                title="t-SNE-raw-data", 
                file_name=f"raw-{file}-{date}", 
                features_list=[study_name, factor_of_interest], #feature list has two values: study_name and factor_of_interest
                output=outputs)
            NMDS(variables,
                target_bioproject,
                target_diagnosis,
                title="NMDS-raw-data",
                file_name=f"raw-{file}-{date}",
                features_list=[study_name, factor_of_interest],
                output=outputs)
            PCoA(raw_data, target_bioproject, target_diagnosis,
                 title="PCoA (Aitchison) - raw data",
                 file_name=f"raw-{file}-{date}",
                 features_list=[study_name, factor_of_interest],
                 output=outputs, distance="aitchison")
            dissimilarity_heatmap(raw_data, study_name, outputs,
                                  title=f"dissimilarity-raw-{file}-{date}")
            if glb.run_neighbourhood_metrics:
                graph_connectivity_plot(raw_data, [factor_of_interest, study_name], outputs,
                                        title=f"graph-connectivity-raw-{file}-{date}")

# Variability before and after
data = pd.read_excel(f"{outputs}/final-calculations{date}.xlsx").round(2)
results_groups = data.groupby("datasetName", sort=False)
for dataset, group in results_groups:
    # Sort the group by study ID (batch) for consistent ordering
    group_sorted = group.sort_values(f"permanova-{study_name}-R2-corrected", ascending=False)
    # Reshape the data (wide-format data into long-format data)
    # to plot barplot with seaborn long-format data is needed
    # wide format:
    #   sampleID        method      permanova-batch-R2-corrected        permanova-diagnosis-R2-corrected 
    #   sample1         wPLSDA      67.9                                21.1
    # long format:
    #   method          metric                                  value
    #   wPLSDA          permanova-batch-R2-corrected            67.9
    #   wPLSDA          permanova-diagnosis-R2-corrected        21.1
    
    # Split into two parts: uncorrected and other rows
    uncorrected = group_sorted[group_sorted["method"] == "uncorrected"]
    corrected = group_sorted[group_sorted["method"] != "uncorrected"]
    # Melt separately
    melted_uncorrected = pd.melt(
        uncorrected,
        id_vars=["method"], #columns to keep as it is
        value_vars=[f"permanova-{study_name}-R2", f"permanova-{factor_of_interest}-R2"],
        var_name="metric", #the name of the new column that stores which variable (former column name) each value from
        value_name="value" #the name of the new column that stores the actual values
    )
    melted_corrected = pd.melt(
        corrected,
        id_vars=["method"], #columns to keep as it is
        value_vars=[f"permanova-{study_name}-R2-corrected", f"permanova-{factor_of_interest}-R2-corrected"],
        var_name="metric", #the name of the new column that stores which variable (former column name) each value from
        value_name="value" #the name of the new column that stores the actual values
    )
    # Combine back
    melted_group = pd.concat([melted_uncorrected, melted_corrected], ignore_index=True)
    # Rename legend labels
    melted_group["metric"] = melted_group["metric"].replace({f"permanova-{study_name}-R2-corrected": "Bioproject Variability",
                                                             f"permanova-{factor_of_interest}-R2-corrected": "Diagnosis Variability",
                                                             f"permanova-{study_name}-R2": "Bioproject Variability",
                                                             f"permanova-{factor_of_interest}-R2": "Diagnosis Variability",},)
    from bernard_library import ROLE_COLOURS, style_axes
    plt.figure(figsize=(15, 12))
    ax = sns.barplot(data=melted_group,
                     x="method", #all methods will be printed on x-axis, each method will have two bars
                     y="value", #value is percentage of variability explained by batch and diagnosis/treatment, it reflects the height of each bar
                     hue="metric",  # Use the renamed legend labels
                     errorbar=None,
                     palette={"Bioproject Variability": ROLE_COLOURS['batch'],
                              "Diagnosis Variability": ROLE_COLOURS['phenotype']})
    for i in ax.containers:
        ax.bar_label(i,) #goes through every bar container in the current axes (ax) and label each bar with its height (numerical value)
    plt.tick_params(labelrotation=45) #rotate labels on x-axis (method names) fro 45 degrees
    style_axes(ax, title=f"Dataset: {dataset}", xlabel="",
               ylabel="Percentage of explained variability")
    plt.savefig(f"{outputs}/report/{dataset}-variability-change-{date}.png", dpi=350)

# Dimensionality reduction - corrected data
for dirpath, dirnames, filenames in os.walk(corrected_outputs): #goes through folder with corrected datasets
    for file in smallest_first(dirpath, filenames):
        if file.endswith(".csv") and date in file: #corrected files are stored as .csv files
            # Each corrected file needs to be merged with metadata first
            file_path = os.path.join(dirpath, file)
            #print("File name: ", file_path)
            corrected = pd.read_csv(file_path, low_memory=False)
            try:
                corrected = corrected.set_index("Unnamed: 0")
            except: corrected = corrected.set_index(sample_id_column)
            variables = table_for_dimensionality_reduction_variables(corrected) #returns only numeric columns with standardized values
            target_bioproject = table_for_dimensionality_reduction(corrected, study_name) #dataframe with batch column only
            target_diagnosis = table_for_dimensionality_reduction(corrected, factor_of_interest) #dataframe with factor of interest column only
            PCA(variables, 
                target_bioproject, 
                target_diagnosis, 
                title="PCA-corrected data", 
                file_name=f"corrected-{file}-{date}", 
                features_list=[study_name, factor_of_interest], 
                output=outputs)
            MDS(variables, 
                target_bioproject, 
                target_diagnosis, 
                title="MDS-corrected data", 
                file_name=f"corrected-{file}-{date}", 
                features_list=[study_name, factor_of_interest], 
                output=outputs)
            TSNE(variables, 
                target_bioproject, 
                target_diagnosis, 
                title="t-SNE-corrected data", 
                file_name=f"corrected-{file}-{date}", 
                features_list=[study_name, factor_of_interest], 
                output=outputs)
            NMDS(variables,
                target_bioproject,
                target_diagnosis,
                title="NMDS-corrected data",
                file_name=f"corrected-{file}-{date}",
                features_list=[study_name, factor_of_interest],
                output=outputs)
            PCoA(corrected, target_bioproject, target_diagnosis,
                 title="PCoA (Aitchison) - corrected data",
                 file_name=f"corrected-{file}-{date}",
                 features_list=[study_name, factor_of_interest],
                 output=outputs, distance="aitchison")
            dissimilarity_heatmap(corrected, study_name, outputs,
                                  title=f"dissimilarity-corrected-{file}-{date}")
            if glb.run_neighbourhood_metrics:
                graph_connectivity_plot(corrected, [factor_of_interest, study_name], outputs,
                                        title=f"graph-connectivity-corrected-{file}-{date}")


from bernard_library import batch_dissimilarity_summary, feature_r2_plot, variance_partition_plot

for dataset in full_calculation['datasetName'].dropna().unique():
    dataset_rows = full_calculation[full_calculation['datasetName'] == dataset]

    dissimilarity_records = []
    for (stored_dataset, stored_method), value in glb.batch_dissimilarity.items():
        if stored_dataset == dataset and value is not None:
            dissimilarity_records.append({'method': stored_method, 'excess': value})
    batch_dissimilarity_summary(dissimilarity_records, outputs,
                                title=f"{dataset}-batch-dissimilarity-{date}")

    r2_records = []
    for (stored_dataset, stored_method), values in glb.feature_r2_distributions.items():
        if stored_dataset == dataset and values:
            r2_records.append({'method': stored_method, **values})
    r2_records.sort(key=lambda entry: (entry['method'] != 'uncorrected', entry['method']))
    feature_r2_plot(r2_records, outputs, f"{dataset}-feature-r2-{date}",
                    factor_of_interest, study_name)

    partition_records = []
    for _, row in dataset_rows.iterrows():
        method_label = row['method'] if isinstance(row['method'], str) else 'uncorrected'
        suffix = '' if method_label == 'uncorrected' else '-corrected'
        record = {'method': method_label}
        for part in ('batch-only', 'phenotype-only', 'shared', 'unexplained'):
            record[part] = row.get(f'varpart-{part}{suffix}')
        if any(record[part] is not None and pd.notna(record[part])
               for part in ('batch-only', 'phenotype-only', 'shared', 'unexplained')):
            partition_records.append(record)
    partition_records.sort(key=lambda entry: (entry['method'] != 'uncorrected', entry['method']))
    variance_partition_plot(partition_records, outputs, f"{dataset}-variance-partition-{date}")

image_dir = f"{outputs}/report" #location of images for pdf
output_dir = outputs #where to store pdf report
from bernard_library import create_pdf
os.makedirs(output_dir, exist_ok=True) #creates directory
# Group images by dataset
datasets = {} #dictionary with file names as keys and image names as values in a list
for dirpath, dirnames, filenames in os.walk(raw_data_folder): #goes through raw data folder to get all datasets that have been processed
    for file in smallest_first(dirpath, filenames):
        if file.startswith("."):  # Skip hidden files like
            continue #skip the rest of this loop iteration and move to the next file
        if "metadata" not in file and "config" not in file and "covariates" not in file:
            file = file.split(".", 1)[0]
            if file not in datasets:
                datasets[file] = []
# datasets dictionary contains all files from raw data folder as keys with empty lists a s their values: {'file1': [], 'file2': []}
# Scan directory and categorize images
for file in os.listdir(image_dir): #folder where images for pdf have been stored
    if file.endswith(".png"):
        # Append file to the corresponding dataset
        matching_keys = [key for key in datasets
                         if re.search(rf'(^|[-_]){re.escape(key)}([-_.]|$)', file) and date in file]
        if matching_keys:
            key = max(matching_keys, key=len)
            datasets[key].append(file) # appending image names to lists in datasets dictionary
            # example: {'file1': [image1.png, image2.png], 'file2': [image3.png, image4.png]}
# Generate PDFs for Each Dataset
result_table = pd.read_excel(f"{output_path}/final-calculations{date}.xlsx").round(3)
for dataset, images in datasets.items():
    if images:
        create_pdf(study_name, # batch column, defined in config.json
                   factor_of_interest, # diagnosis/treatment column, defined in config.json
                   select_thresholdSamples, #defined in bernard_cfg.txt
                   select_thresholdFeatures, #defined in bernard_cfg.txt
                   dataset, # key in datasets
                   result_table, # calculation excel
                   images, # value in datasets
                   date, # timestamp of the run
                   image_dir=image_dir, # folder where images for pdf have been stored
                   output_dir=output_dir) # where to store pdf report
        

# When create_out_zip is set to Yes in bernard_cfg.txt file, the resulting output directory is packed into a ZIP archive with name.
# Dafault value is No.
create_out_zip = params.opt_bool_N('create_out_zip') 
if create_out_zip:
    print("\nCreating output ZIP file.. ", end='')
    bml.zip_util.create_zip_from_directory(outputs, f'{bernard_folder}/bernard-out-{date}.zip')
    print("OK.")


report_time = time.time() - start_time_report

from bernard_library import write_run_manifest
write_run_manifest(
    output_path, date,
    settings={
        'evaluation_space': glb.evaluation_space,
        'select_thresholdSamples': select_thresholdSamples,
        'select_thresholdFeatures': select_thresholdFeatures,
        'outlier_contamination': glb.outlier_contamination,
        'diagnosis_variability_retention': retained_variability,
        'diagnosis_variability_lower_limit': lower_limit_variability,
        'run_permdisp': glb.run_permdisp,
        'permdisp_permutations': glb.permdisp_permutations,
        'run_auroc': glb.run_auroc,
        'neighbourhood_k': getattr(glb, 'neighbourhood_k', None),
        'config_file': cfg_file_name,
        'random_seed': glb.random_seed,
        'permanova_permutations': glb.permanova_permutations,
        'significance_alpha': glb.significance_alpha,
        'kbet_alpha': glb.kbet_alpha,
        'auroc_trees': glb.auroc_trees,
        'auroc_folds': glb.auroc_folds,
        'pvca_variance_threshold': glb.pvca_variance_threshold,
        'pvca_max_components': glb.pvca_max_components,
        'tsne_perplexity': glb.tsne_perplexity,
        'figure_dpi': glb.figure_dpi,
        'variability_threshold_step': variability_step,
        'correction_methods': [method.label for method in selected_methods],
        'max_parallel_methods': max_parallel_methods,
    },
    datasets=[{'dataset': str(row['datasetName']),
               'samples': row.get('new number of samples'),
               'features': row.get('new number of features')}
              for _, row in full_calculation.drop_duplicates(subset=['datasetName']).iterrows()],
    method_outcomes=method_outcomes)

for dataset_timing in dataset_timings:
    print(f"\nTotal runtime for data cleaning with statistics of {dataset_timing['name']} is "
          f"{dataset_timing['cleaning_with_statistics']}")
    print(f"Total runtime for data cleaning of {dataset_timing['name']} is "
          f"{dataset_timing['cleaning']}")

total_method_time = 0.0
for method_label, method_runtime in method_runtimes:
    total_method_time = total_method_time + method_runtime
    print(f"Total runtime for {method_label} is {method_runtime:.1f} seconds")

print(f"\nThe correction methods took {total_method_time:.1f} seconds of work in total, "
      f"{max_parallel_methods} at a time.")

end_time_full = time.time()
total_runtime = end_time_full - start_time_full
print(f"Total BERNARD runtime is {total_runtime}") 

runtime_log = settings_values.get('runtime_log')

if runtime_log is None or str(runtime_log).strip().lower() in ('', 'none', 'no'):
    print("\nNo runtime table was written (runtime_log is switched off).")
else:
    runtime_log = make_abs_path(str(runtime_log).strip())

    runtime_rows = bruntimes.build_rows(
        dataset_timings,
        method_runtimes,
        shared={
            'run':                  full_date.strftime('%Y-%m-%d %H:%M:%S'),
            'correction_and_scoring': correction_and_scoring_time,
            'selection':            selection_time,
            'report':               report_time,
            'total':                total_runtime,
            'max_parallel_methods': max_parallel_methods,
        })

    written = bruntimes.append(runtime_log, runtime_rows)

    if written is not None:
        print(f"\n{len(runtime_rows)} row(s) added to the runtime table {runtime_log}, "
              f"which now holds {written}.")

print("\nBernard finished processing.")

