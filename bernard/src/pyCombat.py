import glb

def merge_dataframes(df1, df2):
    import pandas as pd
    # Concatenate the dataframes along the index
    merged_df = pd.concat([df1, df2], axis=0)
    # Group by the index and aggregate the values
    merged_df = merged_df.groupby(merged_df.index).first()

    return merged_df

def combat():
    import numpy as np
    import pandas as pd
    import traceback
    from inmoose.pycombat import pycombat_norm # inmoose: https://github.com/epigenelabs/inmoose/tree/master
    import os
    import json

    bernard_folder = glb.bernard_folder

    raw_data_folder = bernard_folder + "/raw-data"
    outputs = f"{bernard_folder}/outputs"
    corrected_outputs = f"{outputs}/corrected"
    clean_data = f"{bernard_folder}/outputs/cleaned"

    # Variables from config.json file
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])
    sample_id_column = str(config["sample_id_column"])

    for file in os.listdir(clean_data):
        if file.startswith("."):  # Skip hidden files like
            continue #skip the rest of this loop iteration and move to the next file
        file_path = os.path.join(clean_data, file)
        print(f"File name: {file}")

        dataset = pd.read_csv(file_path, low_memory=False)
        try:
            dataset = dataset.set_index("Unnamed: 0")
        except: dataset = dataset.set_index(sample_id_column)

        dataset.drop(list(dataset.filter(regex='Unnamed:')), axis=1, inplace=True)
        corrected_dataset = dataset

        metadata = [study_name, factor_of_interest]
        with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
            covariates = [line.strip() for line in covariate_file]
        metadata.extend(covariates)

        existing_metadata = [col for col in metadata if col in corrected_dataset.columns]
        # Drop only the columns that are present
        variables = corrected_dataset.drop(columns=existing_metadata) #feature values
        non_variables = corrected_dataset[existing_metadata]
        corrected_dataset['labels'], _ = pd.factorize(corrected_dataset[study_name]) #converting categorical variable into numeric labels in new column "labels"
        corrected_dataset = corrected_dataset.drop(study_name, axis=1) #datasets has now labeled batch informations
        batch = corrected_dataset["labels"].tolist()
        variables = variables.T ## the indices correspond to the feature names, the column names correspond to the sample names
        variables = variables.loc[(variables != 0).any(axis=1)] #keeps only rows that have at least one nonzero value, rows with only zeros will break or distort pycombat_norm()

        values = variables.astype(float)
        is_counts = np.allclose(values.values, np.round(values.values))
        positive = values.values[values.values > 0]
        offset = 1.0 if is_counts or positive.size == 0 else positive.min() / 2
        log_values = np.log(values + offset)

        phenotype = dataset[factor_of_interest].astype(str).tolist()
        try:
            if len(set(batch)) < 2:
                raise ValueError(f"pyCombat requires at least two {study_name} levels to run.")
            try:
                data_corrected = pycombat_norm(log_values, batch, covar_mod=phenotype)
            except ValueError as e:
                if "confounded" not in str(e):
                    raise
                print(f"{factor_of_interest} is confounded with {study_name} ({e}); "
                      f"correcting without it as a covariate.")
                data_corrected = pycombat_norm(log_values, batch)
            data_corrected = data_corrected.transpose()
            data_corrected = merge_dataframes(data_corrected, non_variables)
            data_corrected.to_csv(f"{corrected_outputs}/{file[:-4]}_pyCombat-tmp.csv")
            print("pyCombat finished.")
        except Exception as e:
            print(f"pyCombat failed for {file}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python3 pyCombat.py <folder of the dataset>")
        sys.exit(-1)

    glb.bernard_folder = sys.argv[1].rstrip('/')
    combat()
