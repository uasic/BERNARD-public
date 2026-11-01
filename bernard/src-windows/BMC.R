suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(MBECS)
  library(readr)
  library(phyloseq)
  library(ruv)
  library(preprocessCore)
  library(sva)
  library(jsonlite)
  
  batch_correction_method <- "BMC"
  
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
  
  # Load metadata
  metadata_file <- file.path(bernard_folder, "raw-data", "covariates.txt")
  metadata_columns <- readLines(metadata_file, warn=FALSE)
  
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
      tryCatch({
      # Load data
      full_file_path <- file.path(input_folder, file)
      data <- read_csv(full_file_path, show_col_types = FALSE)
      data <- as.data.frame(data)
      cat("Processing file:", file, "\n")
      #View(data)
      
      # Rename "Unnamed: 0" to the sample_id_column (e.g., "run") if it exists
      if ("Unnamed: 0" %in% colnames(data)) {
        colnames(data)[colnames(data) == "Unnamed: 0"] <- sample_id_column
      }
      run_column <- data[[sample_id_column]]
      study_name_column <- data[[study_name]]
      factor_of_interest_column <- data[[factor_of_interest]]
      
      rownames(data) <- data[[sample_id_column]]
      data[[sample_id_column]] <- NULL
  
      # Remove unnecessary columns
      data <- data[, !(names(data) %in% metadata_columns)] # Removal of metadata
      data$...1 <- NULL
      #View(data)
  
      bioProject <- data[[study_name]]
      diagnosis <- data[[factor_of_interest]]
      data[[study_name]] <- NULL
      data[[factor_of_interest]] <- NULL
      #View(data)
  
      values <- as.matrix(data)
      storage.mode(values) <- "double"
      log_values <- log(values + log_offset(values))
      data <- as.data.frame(log_values - rowMeans(log_values), check.names = FALSE)

      # Perform BMC
      data_bmc <- data
      for (batch in unique(bioProject)) {
        batch_indices <- which(bioProject == batch)
        batch_mean <- colMeans(data[batch_indices, ])
        data_bmc[batch_indices, ] <- sweep(data[batch_indices, ], 2, batch_mean)
      }
  
      data_bmc <- as.data.frame(data_bmc)
      data_bmc[[sample_id_column]] <- run_column  # Add back the "run" column
      data_bmc[[study_name]] <- study_name_column
      data_bmc[[factor_of_interest]] <- factor_of_interest_column
      rownames(data_bmc) <- data_bmc[[sample_id_column]]
      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_bmc-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      #View(data_bmc)
      write_csv(data_bmc, output_file)
      print("BMC finished.")
  
    }, error = function(e) {
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})