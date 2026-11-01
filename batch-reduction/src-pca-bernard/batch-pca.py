# ---------------------
# Run from terminal
# ---------------------
# python3 BERNARD/batch-reduction/src-pca-bernard/batch-pca.py \
#   BERNARD/batch-reduction/bernard_pca_cfg.txt \
#   BERNARD/batch-reduction
# ---------------------
# Load dependencies
# ---------------------
import pandas as pd
import os
import datetime
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=pd.errors.SettingWithCopyWarning)
import json
from sklearn.decomposition import PCA

# ---------------------
# General settings
# ---------------------

import sys
import bml.params as params
import bml.files as bfiles

print("\n\nBernard V1.0, date 2025_04_24\n\n")

if len(sys.argv) != 3:
    print("Error, invalid command line.\n\n")
    print("Usage: Bernard /abs/path/to_config_file.txt /abs/path/to_work_dir\n\nAborting.")
    sys.exit(-1)

cfg_file_name = sys.argv[1]

params_status = params.read_file(sys.argv[1], True)

if len(params_status[1]) != 0:
    print("Error(s) found when parsing configuration file:")

    for s in params_status[1]:
        print(s)

    sys.exit(-1)

###############################################################################

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
        return sys.argv[2].rstrip('/') + in_path[1:]

    if in_path[0] != '/':
        return sys.argv[2].rstrip('/') + '/' + in_path

    return in_path

###############################################################################

bernard_input = params.opt_string('bernard_input', default=None)

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

###############################################################################

import glb
glb.bernard_folder = bernard_folder

raw_data_folder = bernard_folder + "/raw-data"
glb.raw_data_folder = raw_data_folder

outputs = bernard_folder + "/outputs"
bfiles.recreate_dir(outputs)

tag_files = bfiles.list_in_dir(raw_data_folder, 'tag.txt', full_path = True)
if len(tag_files) == 1:
    bfiles.copy_to_dir(tag_files[0], outputs)

# ---------------------
# Reducing dimensionality
# ---------------------

# Define what are names of sample ID, study ID and phenotype columns
with open(f"{raw_data_folder}/config.json", "r") as config_file:
    config = json.load(config_file)

sample_id_column = str(config["sample_id_column"])
factor_of_interest = str(config["factor_of_interest"])

# Define what are batches in dataset (country, age, diet...)
batches = []
with open(f"{raw_data_folder}/batches.txt", "r") as covariate_file:
        batch = [line.strip() for line in covariate_file]
        print("Batches:")
        print(batch)
batches.extend(batch)
print(batches)

# Set the date to identify outputs of anlysis
full_date = datetime.datetime.now()
date = str(full_date)
date = date[:-7].replace(" ", "-").replace(":", "")

# Reducing dimensionality every dataset in raw-data folder
for data_file in os.listdir(raw_data_folder):
    print("Reducing dimensionality in every dataset in raw-data folder...")
    if data_file.startswith(".") or "metadata" in data_file or data_file.endswith(".txt") or data_file.endswith(".json"):  # Skip hidden files like .DS_Store and non-csv files
        continue
    filepath = os.path.join(raw_data_folder, data_file)
    print(f"Checking directory: {raw_data_folder}")
    print(f"Exists: {os.path.exists(raw_data_folder)}")
    print(f"Is Directory: {os.path.isdir(raw_data_folder)}")
    print(os.listdir(raw_data_folder))
    print(data_file)
    input_folder = f"{raw_data_folder}" # raw inputs from both analysis
    output_path = f"{outputs}" # processed data stored here
    data = pd.read_csv(filepath, low_memory=False).set_index(sample_id_column)

    # Check that every batch column exists and every sample has a value in it
    missing_columns = [b for b in batches if b not in data.columns]
    if len(missing_columns) != 0:
        print(f"\nError: batch column(s) {missing_columns} not found in {data_file}. Aborting.\n")
        sys.exit(-1)
    batches_data = data[batches]
    empty_cells = batches_data.isna() | batches_data.astype(str).apply(lambda col: col.str.strip() == "")
    if empty_cells.any().any():
        print(f"\nError: empty cells in batch columns of {data_file}; every sample needs a value in every batch column.")
        for b in batches:
            empty_samples = list(empty_cells.index[empty_cells[b]])
            if len(empty_samples) != 0:
                print(f"  {b}: {len(empty_samples)} sample(s) without a value: {', '.join(map(str, empty_samples))}")
        print("Aborting.\n")
        sys.exit(-1)

    batches_encoded = pd.get_dummies(batches_data, columns=batches)
        
    #Initialize PCA with 1 component
    pca = PCA(n_components=1)
    # Fit PCA and transform the encoded data
    batches_pca = pca.fit_transform(batches_encoded)
    # Convert the result to a DataFrame (optional but useful for merging)
    batches_pca_df = pd.DataFrame(batches_pca, index=batches_encoded.index, columns=['batch'])
    # Optionally, add the PCA result back to the original data
    data_with_pca = data.join(batches_pca_df).drop(columns=batches)
    print(batches_pca_df.head())
    print(data_with_pca.head())
    dataset_name = os.path.splitext(data_file)[0]
    data_with_pca.to_csv(f"{output_path}/{dataset_name}-reduced.csv")
    print(f"Dataframe is saved in {dataset_name}-reduced.csv file.")
    metadata = data_with_pca[['batch', factor_of_interest]]
    metadata.to_csv(f"{output_path}/metadata-{dataset_name}-reduced.csv")

print("Dimensionality reduction finished.")