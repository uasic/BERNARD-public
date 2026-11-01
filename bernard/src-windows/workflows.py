import glb

def workflow(dataset, processing, raw_data_folder, file, output, thresholdSamples, thresholdFeatures):
    import json
    import sys
    # Variables defined in bernard_cfg.txt file
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])
    sample_id_column = str(config["sample_id_column"])
    print("In workflow 1 all NaN and negative values are replaced with 0.")
    print(f"Features that have value 0 in more than {thresholdFeatures*100} percentage of samples will be removed.")
    print(f"Samples that have value 0 in more than {thresholdSamples*100} percentage of features will be removed.")
    
    columns_raw = [
        "datasetName",
        "processing",
        "initial number of samples", "initial number of features",
        "new number of samples", "new number of features",
        "percentage of removed samples", "percentage of removed features",
    ]
    covariates = [study_name, factor_of_interest]
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
            metadata = [line.strip() for line in covariate_file]
            print("covariate file content")
            print("Metadata:", metadata)
    covariates.extend(metadata)
    print(covariates)
    from bernard_library import lisi_name
    for covariate in covariates:
        columns_raw.append(f"permanova-{covariate}-p-value")
        columns_raw.append(f"permanova-{covariate}-F-value")
        columns_raw.append(f"permanova-{covariate}-R2")
        columns_raw.append(f"permdisp-{covariate}-p-value")
        columns_raw.append(f"permdisp-{covariate}-F-value")
        columns_raw.append(f"silhouette-{covariate}")
        columns_raw.append(f"kBET-{covariate}-acceptance")
        columns_raw.append(f"{lisi_name(covariate, study_name, factor_of_interest)}-{covariate}")
        columns_raw.append(f"graph-connectivity-{covariate}")
        columns_raw.append(f"alignment-score-{covariate}")
        columns_raw.append(f"alignment-score-{covariate}-max")
        columns_raw.append(f"entropy-score-{covariate}")
        columns_raw.append(f"features-associated-{covariate}-percent")
    columns_raw.append(f"AUROC-{factor_of_interest}-cv")
    columns_raw.append(f"AUROC-{factor_of_interest}-lobo")
    for component in ("batch", "phenotype", "interaction", "residual"):
        columns_raw.append(f"pvca-{component}-percent")
    for part in ("batch-only", "phenotype-only", "shared", "unexplained"):
        columns_raw.append(f"varpart-{part}")
    columns_raw.append("design-balance-cramers-v")
    columns_raw.append("design-balance-p-value")
    columns_raw.append("design-balance-verdict")
    columns_raw.append("design-balance-counts")
    raw_dict = {key: None for key in columns_raw}

    # Assigning values in each column for current raw dataset file
    raw_dict["datasetName"] = file
    raw_dict["processing"] = processing
    number_samples = len(dataset.axes[0]) #number of rows
    number_features = len(dataset.axes[1]) #number of columns
    #print("Initial dataset shape:", dataset.shape)
    raw_dict['initial number of samples'] = number_samples
    raw_dict['initial number of features'] = number_features
    #print("\nCleaning the data...")
    import time
    start_time = time.time()
    from bernard_library import data_cleaning
    from bernard_library import samples_selection
    dataset = samples_selection(dataset, threshold=thresholdSamples)
    print("Dataframe shape after sample selection")
    print(dataset.shape)
    #print("samples ", dataset.shape)
    dataset = data_cleaning(dataset, threshold=thresholdFeatures)
    print("Dataframe shape after sample selection")
    print(dataset.shape)
    #print("features ", dataset.shape)
    dataset.rename_axis(sample_id_column, inplace=True) #sets the name of the index to sample_id_column
    #print("Numbers of features and samples in a dataframe have been updated...")
    new_number_samples = len(dataset.axes[0])
    new_number_features = len(dataset.axes[1])
    raw_dict["new number of samples"] = new_number_samples
    raw_dict['new number of features'] = new_number_features
    raw_dict["percentage of removed samples"] = 100 - (new_number_samples/number_samples)*100
    raw_dict['percentage of removed features'] = 100 - (new_number_features/number_features)*100
    end_time = time.time()
    data_cleaning_time = end_time - start_time
    #print(f"Data cleaning runtime for file {file} is {data_cleaning_time}.")
    dataset.drop(list(dataset.filter(regex='Unnamed:')), axis=1, inplace=True)
    cleaned_dataset_name = f"{output}/cleaned/clean-{file}" #saving cleaned dataset here
    print(f"Saving cleaned dataset as {cleaned_dataset_name}")
    
    from bernard_library import merge_dataframes
    import pandas as pd
    metadata = pd.read_csv(f"{raw_data_folder}/metadata.csv").set_index(sample_id_column)
    metadata = metadata.loc[metadata.index.isin(dataset.index)]
    #Drop columns not present in covariates list
    print("Covariates:", covariates)
    metadata = metadata[covariates]
    # filtering samples: only samples with available data needs to be included from metadata dataframe
    dataset = merge_dataframes(metadata, dataset)
    try: # If raw input file is tsv, the suffix needs to be replaced with csv
        cleaned_dataset_name_final = cleaned_dataset_name.replace("tsv", "csv")
    except: cleaned_dataset_name_final = cleaned_dataset_name
    dataset.to_csv(cleaned_dataset_name_final) # Cleaned file is saved.

    ########################### PERMANOVA & VARIABILITY PERCENTAGE EXPLANATION  ###############################################################################################

    from bernard_library import distance_based_metrics
    from bernard_library import classification_auroc
    for covariate in covariates:

        try:
            result = distance_based_metrics(dataset, feature=covariate)
            if result is None:
                #raise ValueError(f"Permanova returned None for {covariate}")
                sys.exit(f"ERROR: PERMANOVA returned None for {covariate}")
            raw_dict[f'permanova-{covariate}-p-value'] = result['permanova-p-value']
            raw_dict[f'permanova-{covariate}-F-value'] = result['permanova-F-value']
            raw_dict[f'permanova-{covariate}-R2'] = result['permanova-R2']
            raw_dict[f'permdisp-{covariate}-p-value'] = result['permdisp-p-value']
            raw_dict[f'permdisp-{covariate}-F-value'] = result['permdisp-F-value']
            raw_dict[f'silhouette-{covariate}'] = result['silhouette']
            raw_dict[f'kBET-{covariate}-acceptance'] = result['kBET']
            raw_dict[f'{lisi_name(covariate, study_name, factor_of_interest)}-{covariate}'] = result['LISI']
            raw_dict[f'graph-connectivity-{covariate}'] = result['graph-connectivity']
            raw_dict[f'alignment-score-{covariate}'] = result['alignment-score']
            raw_dict[f'alignment-score-{covariate}-max'] = result['alignment-score-max']
            raw_dict[f'entropy-score-{covariate}'] = result['entropy-score']
        except Exception as e:
            print(f"ERROR: PERMANOVA failed for {covariate} with error: {e}")

    from bernard_library import feature_association
    for covariate in covariates:
        try:
            raw_dict[f'features-associated-{covariate}-percent'] = feature_association(dataset, covariate)
        except Exception as e:
            print(f"ERROR: per-feature association failed for {covariate}: {e}")

    from bernard_library import pvca, variance_partitioning, design_balance
    try:
        components = pvca(dataset, study_name, factor_of_interest)
        if components:
            for component, value in components.items():
                raw_dict[f'pvca-{component}-percent'] = value
    except Exception as e:
        print(f"ERROR: PVCA failed with error: {e}")
    try:
        parts = variance_partitioning(dataset, study_name, factor_of_interest)
        if parts:
            for part, value in parts.items():
                raw_dict[f'varpart-{part}'] = value
    except Exception as e:
        print(f"ERROR: variance partitioning failed with error: {e}")
    try:
        balance = design_balance(dataset, study_name, factor_of_interest)
        if balance:
            raw_dict['design-balance-cramers-v'] = balance['cramers-v']
            raw_dict['design-balance-p-value'] = balance['p-value']
            raw_dict['design-balance-verdict'] = balance['verdict']
            raw_dict['design-balance-counts'] = balance['counts']
            print(f"\nDesign balance ({study_name} against {factor_of_interest}): "
                  f"Cramer's V = {balance['cramers-v']:.3f} - {balance['verdict']}")
    except Exception as e:
        print(f"ERROR: design balance failed with error: {e}")


    from bernard_library import mean_between_group_excess, feature_r2, dataset_key
    try:
        key = (dataset_key(file), 'uncorrected')
        glb.batch_dissimilarity[key] = mean_between_group_excess(dataset, study_name)
        glb.feature_r2_distributions[key] = {
            'batch': feature_r2(dataset, study_name),
            'phenotype': feature_r2(dataset, factor_of_interest),
        }
    except Exception as e:
        print(f"ERROR: cross-method figures data failed: {e}")

    try:
        auroc = classification_auroc(dataset, dataset_name=file, method='uncorrected')
        raw_dict[f'AUROC-{factor_of_interest}-cv'] = auroc['cv']
        raw_dict[f'AUROC-{factor_of_interest}-lobo'] = auroc['lobo']
    except Exception as e:
        print(f"ERROR: AUROC failed with error: {e}")
    return raw_dict, dataset, data_cleaning_time

def workflow_for_corrected(dataset, file, method):

    bernard_folder = glb.bernard_folder

    raw_data_folder = bernard_folder + "/raw-data"
    
    import json
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])
    sample_id_column = str(config["sample_id_column"])
    try:
        dataset.set_index(sample_id_column)
    except:pass
    #from bernard_library import replacing_nan
    #dataset = replacing_nan(dataset)
    covariates = [study_name, factor_of_interest]
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
            metadata = [line.strip() for line in covariate_file]
            print("Metadata:", metadata)
    covariates.extend(metadata)
    print("Covariates", covariates)

    columns_corrected = [
    "datasetName",
    "method"
    ]

    from bernard_library import lisi_name
    for covariate in covariates:
        columns_corrected.append(f"permanova-{covariate}-p-value-corrected")
        columns_corrected.append(f"permanova-{covariate}-F-value-corrected")
        columns_corrected.append(f"permanova-{covariate}-R2-corrected")
        columns_corrected.append(f"permdisp-{covariate}-p-value-corrected")
        columns_corrected.append(f"permdisp-{covariate}-F-value-corrected")
        columns_corrected.append(f"silhouette-{covariate}-corrected")
        columns_corrected.append(f"kBET-{covariate}-acceptance-corrected")
        columns_corrected.append(f"{lisi_name(covariate, study_name, factor_of_interest)}-{covariate}-corrected")
        columns_corrected.append(f"graph-connectivity-{covariate}-corrected")
        columns_corrected.append(f"alignment-score-{covariate}-corrected")
        columns_corrected.append(f"entropy-score-{covariate}-corrected")
        columns_corrected.append(f"features-associated-{covariate}-percent-corrected")
    columns_corrected.append(f"AUROC-{factor_of_interest}-cv-corrected")
    columns_corrected.append(f"AUROC-{factor_of_interest}-lobo-corrected")
    for component in ("batch", "phenotype", "interaction", "residual"):
        columns_corrected.append(f"pvca-{component}-percent-corrected")
    for part in ("batch-only", "phenotype-only", "shared", "unexplained"):
        columns_corrected.append(f"varpart-{part}-corrected")
    #print(columns_corrected)# Convert list to dictionary with None as initial values
    corrected_dict = {key: None for key in columns_corrected}
    #print(corrected_dict)

    corrected_dict["datasetName"] = file
    corrected_dict["method"] = method

    ########################### PERMANOVA & VARIABILITY PERCENTAGE EXPLANATION  ###############################################################################################

    print(f"\nPermanova, PERMDISP, kBET, LISI, graph connectivity and AUROC after {method} in progress...", end='')
    from bernard_library import distance_based_metrics
    from bernard_library import classification_auroc
    for covariate in covariates:
        #print(f"Current covariate: {covariate}")
        try:
            result = distance_based_metrics(dataset, feature=covariate)

            if result is None:
                raise ValueError(f"Permanova returned None for {covariate}")

            corrected_dict[f'permanova-{covariate}-p-value-corrected'] = result['permanova-p-value']
            corrected_dict[f'permanova-{covariate}-F-value-corrected'] = result['permanova-F-value']
            corrected_dict[f'permanova-{covariate}-R2-corrected'] = result['permanova-R2']
            corrected_dict[f'permdisp-{covariate}-p-value-corrected'] = result['permdisp-p-value']
            corrected_dict[f'permdisp-{covariate}-F-value-corrected'] = result['permdisp-F-value']
            corrected_dict[f'silhouette-{covariate}-corrected'] = result['silhouette']
            corrected_dict[f'kBET-{covariate}-acceptance-corrected'] = result['kBET']
            corrected_dict[f'{lisi_name(covariate, study_name, factor_of_interest)}-{covariate}-corrected'] = result['LISI']
            corrected_dict[f'graph-connectivity-{covariate}-corrected'] = result['graph-connectivity']
            corrected_dict[f'alignment-score-{covariate}-corrected'] = result['alignment-score']
            corrected_dict[f'entropy-score-{covariate}-corrected'] = result['entropy-score']
        except Exception as e:
            print(f"Error processing {covariate}: {e}")

    from bernard_library import feature_association, pvca, variance_partitioning
    for covariate in covariates:
        try:
            corrected_dict[f'features-associated-{covariate}-percent-corrected'] = feature_association(dataset, covariate)
        except Exception as e:
            print(f"ERROR: per-feature association failed for {covariate}: {e}")
    try:
        components = pvca(dataset, study_name, factor_of_interest)
        if components:
            for component, value in components.items():
                corrected_dict[f'pvca-{component}-percent-corrected'] = value
    except Exception as e:
        print(f"ERROR: PVCA failed with error: {e}")
    try:
        parts = variance_partitioning(dataset, study_name, factor_of_interest)
        if parts:
            for part, value in parts.items():
                corrected_dict[f'varpart-{part}-corrected'] = value
    except Exception as e:
        print(f"ERROR: variance partitioning failed with error: {e}")


    from bernard_library import mean_between_group_excess, feature_r2, dataset_key
    try:
        key = (dataset_key(file), method)
        glb.batch_dissimilarity[key] = mean_between_group_excess(dataset, study_name)
        glb.feature_r2_distributions[key] = {
            'batch': feature_r2(dataset, study_name),
            'phenotype': feature_r2(dataset, factor_of_interest),
        }
    except Exception as e:
        print(f"ERROR: cross-method figures data failed: {e}")

    try:
        auroc = classification_auroc(dataset, dataset_name=file, method=method)
        corrected_dict[f'AUROC-{factor_of_interest}-cv-corrected'] = auroc['cv']
        corrected_dict[f'AUROC-{factor_of_interest}-lobo-corrected'] = auroc['lobo']
    except Exception as e:
        print(f"ERROR: AUROC failed with error: {e}")
    print("done.")

    import pandas as pd
    corrected_calculations = pd.DataFrame([corrected_dict])
    return corrected_calculations
