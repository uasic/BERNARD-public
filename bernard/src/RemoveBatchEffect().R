suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(readr)
  library(limma)
  library(jsonlite)
  
  batch_correction_method <- "RemoveBatchEffect"
  
  set.seed(42)
  
  bernard_folder <- args[1]
  #bernard_folder <- "/Users/uasic/Desktop/BERNARD/bernard/demo"
  print(bernard_folder)
  
  input_folder <- file.path(bernard_folder, "outputs", "cleaned")
  output_folder <- file.path(bernard_folder, "outputs", "corrected")
  raw_data <- file.path(bernard_folder, "raw-data")
  
  csv_inputs <- list.files(path = input_folder, pattern = "\\.csv$", full.names = FALSE)
  csv_inputs <- setdiff(csv_inputs, "metadata.csv")
  csv_inputs <- csv_inputs[order(file.info(file.path(input_folder, csv_inputs))$size,
                                 na.last = TRUE)]
  #print(csv_inputs)
  
  # Load metadata
  metadata_file = file.path(raw_data, "covariates.txt")
  metadata_columns <- readLines(metadata_file, warn=FALSE)
  #print(metadata_columns)
  
  # Load JSON config
  config_file <- file.path(raw_data, "config.json")
  config <- fromJSON(config_file)
  # Extract column names from config
  study_name <- config$study_name
  factor_of_interest <- config$factor_of_interest
  sample_id_column <- config$sample_id_column

  if (!is.null(config$random_seed)) {
    set.seed(as.integer(config$random_seed))
  }
  
  is_integer_valued <- function(values) all(abs(values - round(values)) < 1e-8)
  log_offset <- function(values) {
    values <- values[is.finite(values)]
    if (is_integer_valued(values)) return(1)
    positive <- values[values > 0]
    if (length(positive) == 0) return(1)
    min(positive) / 2
  }

  for (file in csv_inputs) {
    dataset_seed <- if (!is.null(config$random_seed)) as.integer(config$random_seed) else 42L
    set.seed(dataset_seed)
  
    tryCatch(
      {
        # Load data
        full_file_path <- file.path(input_folder, file)
        data <- read_csv(full_file_path, show_col_types = FALSE)
        data <- as.data.frame(data)
        cat("Processing file:", file, "\n")
  
        # Rename "Unnamed: 0" to the sample_id_column (e.g., "run") if it exists
        if ("Unnamed: 0" %in% colnames(data)) {
          colnames(data)[colnames(data) == "Unnamed: 0"] <- sample_id_column
        }
        
        run_column <- data[[sample_id_column]]
        study_name_column <- data[[study_name]]
        factor_of_interest_column <- data[[factor_of_interest]]
        #View(run_column)
        rownames(data) <- data[[sample_id_column]]
        data[[sample_id_column]] <- NULL
        
        # Remove unnecessary columns
        data <- data[, !(names(data) %in% metadata_columns)]
        data$...1 <- NULL

        #Extracting microbiome data...
        microbiome_data <- data[, !names(data) %in% c(study_name, factor_of_interest)]
        microbiome_data <- as.matrix(microbiome_data)
        microbiome_data[is.nan(microbiome_data)] <- 0
        microbiome_data <- t(microbiome_data)
        microbiome_data <- log(microbiome_data + log_offset(microbiome_data))
        microbiome_data <- as.matrix(microbiome_data)

        batchid <- factor(data[[study_name]])
        phenotype <- factor(data[[factor_of_interest]])
        if (nlevels(batchid) < 2) {
          stop("removeBatchEffect() needs at least two ", study_name, " levels.")
        }
        design <- if (nlevels(phenotype) > 1) model.matrix(~ phenotype) else matrix(1, ncol(microbiome_data), 1)

        data_corrected <- removeBatchEffect(microbiome_data,
                                            batch = batchid,
                                            design = design)

        #View the corrected data and write to file
        data_corrected <- t(data_corrected)
        data_corrected <- as.data.frame(data_corrected)
        data_corrected <- cbind(setNames(data.frame(rownames(data_corrected)), sample_id_column), data_corrected)
        data_corrected[[sample_id_column]] <- run_column  # Add back the "run" column
        data_corrected[[study_name]] <- study_name_column
        data_corrected[[factor_of_interest]] <- factor_of_interest_column
  
        #Saving corrected data...
        # Generate the base name of the file (without path and extension)
        base_name <- tools::file_path_sans_ext(basename(file))  # Extract the base name of the input file
        # Construct the custom output file name with "PLSDA" string
        output_file_name <- paste0(base_name, "_RemoveBatchEffect-tmp.csv")
        # Create the full output file path by combining the output folder and the custom file name
        output_file <- file.path(output_folder, output_file_name)
        # Save the corrected data to the output file
        #View(data_corrected)
        write_csv(data_corrected, output_file)
        print("RemoveBatchEffect finished.")
      }, 
      error = function(e) {
        message("An unexpected error occurred with file: ", file, "\nError: ", conditionMessage(e), "\n")
      }
    )
  }
})