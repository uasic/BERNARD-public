suppressPackageStartupMessages({

  args <- commandArgs(trailingOnly = TRUE)
  
  library(ConQuR)
  library(doParallel) 
  library(readr)
  library(jsonlite)
  batch_correction_method <- "ConQuR"
  
  set.seed(42)
  
  bernard_folder <- args[1]
  #bernard_folder <- here()
  print(bernard_folder)
  
  input_folder <- file.path(bernard_folder, "outputs", "cleaned")
  output_folder <- file.path(bernard_folder, "outputs", "corrected")
  raw_data <- file.path(bernard_folder, "raw-data")
  
  csv_inputs <- list.files(path = input_folder, pattern = "\\.csv$", full.names = FALSE)
  csv_inputs <- setdiff(csv_inputs, "metadata.csv")
  csv_inputs <- csv_inputs[order(file.info(file.path(input_folder, csv_inputs))$size,
                                 na.last = TRUE)]
  
  # Load metadata
  metadata_file = file.path(raw_data, "covariates.txt")
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
  as_count_matrix <- function(values) {
    storage.mode(values) <- "double"
    values[!is.finite(values) | values < 0] <- 0
    if (!is_integer_valued(values) && max(rowSums(values)) <= 100.5) {
      cat("Relative abundances detected; converting to pseudo counts (1e5 per sample).\n")
      library_size <- rowSums(values)
      library_size[library_size == 0] <- 1
      values <- values / library_size * 1e5
    }
    values <- round(values)
    storage.mode(values) <- "integer"
    values
  }

  for (file in csv_inputs) {
    dataset_seed <- if (!is.null(config$random_seed)) as.integer(config$random_seed) else 42L
    set.seed(dataset_seed)
    
    tryCatch(
      {
        #Load data
        cat("Processing file: ", file)
        full_file_path <- file.path(input_folder, file)
        data <- read_csv(full_file_path, show_col_types = FALSE)
        data <- as.data.frame(data)
  
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
        
        metadata_data <- metadata_columns
    
        #Remove unnecessary metadata
        data$...1 <- NULL
        #Generating values...
        values <- data
        values[[study_name]] <- NULL
        values[[factor_of_interest]] <- NULL
        values <- values[, !(names(values) %in% metadata_columns)]
        values <- as.data.frame(as_count_matrix(as.matrix(values)), check.names = FALSE)

        #Generating batchid...
        data[[study_name]] <- factor(data[[study_name]])
        batchid = data[, study_name]
  
        #Generating covar...
        data[[factor_of_interest]] <- factor(data[[factor_of_interest]])
        covar <- data.frame(data[[factor_of_interest]])
        colnames(covar) <- factor_of_interest

        #Batch correction...
        batch_ref <- levels(batchid)[1]
        corrected_data <- suppressWarnings(
          ConQuR(tax_tab=values, covariates = covar, batchid=batchid, batch_ref=batch_ref))
        corrected_data <- cbind(setNames(data.frame(rownames(corrected_data)), sample_id_column), corrected_data)
  
        #Saving corrected data...
        corrected_data <- as.data.frame(corrected_data)
        corrected_data[[sample_id_column]] <- run_column  # Add back the "run" column
        corrected_data[[study_name]] <- study_name_column
        corrected_data[[factor_of_interest]] <- factor_of_interest_column
  
        # Generate the base name of the file (without path and extension)
        base_name <- tools::file_path_sans_ext(basename(file))  # Extract the base name of the input file
        # Construct the custom output file name with "ConQuR" string
        output_file_name <- paste0(base_name, "_ConQuR-tmp.csv")
        # Create the full output file path by combining the output folder and the custom file name
        output_file <- file.path(output_folder, output_file_name)
        # Save the corrected data to the output file
        write_csv(corrected_data, output_file)
        print("ConQuR finished.")
        
      }, error = function(e) {
        # General error for unexpected issues
        message("An unexpected error occurred with file: ", file, "\nError: ", e)
      })
  }
})