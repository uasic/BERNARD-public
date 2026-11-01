suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(MBECS)
  library(readr)
  library(phyloseq)
  library(ruv)
  library(preprocessCore)
  library(sva)
  library(jsonlite)
  batch_correction_method <- "RUV3"
  
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
      cat("Processing file: ", file)
      #View(data)
      
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
      
      #Removing unnecesary columns...
      data <- data[, !(names(data) %in% metadata_columns)]
      data$...1 <- NULL
  
      bioProject <- data[[study_name]]
      diagnosis <- data[[factor_of_interest]]
      data[[study_name]] <- NULL
      data[[factor_of_interest]] <- NULL
      
      #str(data)
      data <- data[sapply(data, is.numeric)]

      values <- as.matrix(data)
      storage.mode(values) <- "double"
      Y <- log(values + log_offset(values))

      phenotype <- factor(diagnosis)
      if (nlevels(phenotype) < 2) {
        stop("RUV-III needs at least two ", factor_of_interest, " groups to build a replicate matrix.")
      }
      if (any(table(phenotype) < 2)) {
        stop("RUV-III needs at least two samples in every ", factor_of_interest,
             " group to use them as pseudo replicates.")
      }
      M <- ruv::replicate.matrix(phenotype)

      control_p_values <- apply(Y, 2, function(feature_values) {
        if (stats::sd(feature_values) == 0) return(1)
        tryCatch(stats::anova(stats::lm(feature_values ~ phenotype))[["Pr(>F)"]][1],
                 error = function(e) 1)
      })
      controls <- !is.na(control_p_values) & control_p_values > 0.05
      cat("Pseudo negative controls: ", sum(controls), " of ", ncol(Y), " features\n", sep = "")
      if (sum(controls) < 2) {
        stop("Fewer than two pseudo negative control features were found, RUV-III cannot be applied.")
      }

      k <- max(1, min(length(unique(bioProject)) - 1, sum(controls) - 1, nrow(Y) - ncol(M)))
      cat("Number of removed unwanted factors (k): ", k, "\n", sep = "")

      # Perform RUV-3
      ruv3_result <- RUVIII(Y = Y, M = M, ctl = controls, k = k)
      #View(ruv3_result)
      
      # Handle RUVIII output
      if (is.matrix(ruv3_result)) {
        corrected_data <- ruv3_result
      } else if (is.list(ruv3_result) && "newY" %in% names(ruv3_result)) {
        corrected_data <- ruv3_result$newY
      } else {
        stop("Unexpected output from RUVIII: ", str(ruv3_result))
      }
      
      # Save corrected data
      corrected_data <- as.data.frame(corrected_data)
      corrected_data[[sample_id_column]] <- run_column  # Add back the "run" column
      corrected_data[[study_name]] <- study_name_column
      corrected_data[[factor_of_interest]] <- factor_of_interest_column
      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_ruv3-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      write_csv(corrected_data, output_file)
      print("RUVIII finished.")
      
    }, error = function(e) {
      # General error for unexpected issues
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})