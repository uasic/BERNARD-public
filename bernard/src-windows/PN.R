suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(MBECS)
  library(readr)
  library(phyloseq)
  library(ruv)
  library(preprocessCore)
  library(sva)
  library(jsonlite)
  batch_correction_method <- "PN"
  
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

  percentile_of_score <- function(control_values, x) {
    n <- length(control_values)
    if (n == 0) return(rep(NA_real_, length(x)))
    sorted_controls <- sort(control_values)
    strictly_below <- findInterval(x, sorted_controls, left.open = TRUE)
    below_or_equal <- findInterval(x, sorted_controls)
    100 * (strictly_below + below_or_equal) / (2 * n)
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
      
      bioProject <- data[[study_name]]
      diagnosis <- data[[factor_of_interest]]
      data[[study_name]] <- NULL
      data[[factor_of_interest]] <- NULL
      
      control_level <- config$control_level
      phenotype_values <- as.character(diagnosis)
      phenotype_levels <- unique(phenotype_values)
      if (is.null(control_level)) {
        guessed <- phenotype_levels[grepl("^(control|controls|healthy|hc|normal|td|typical.*)$",
                                          phenotype_levels, ignore.case = TRUE)]
        if (length(guessed) >= 1) {
          control_level <- guessed[1]
        } else {
          control_level <- names(sort(table(phenotype_values), decreasing = TRUE))[1]
          message("No \"control_level\" in config.json and no obvious control group name found. ",
                  "Using the most frequent ", factor_of_interest, " value ('", control_level,
                  "') as the control group.")
        }
      }
      if (!control_level %in% phenotype_levels) {
        stop("control_level '", control_level, "' does not appear in column ", factor_of_interest)
      }
      cat("Control group used as the reference distribution: ", control_level, "\n", sep = "")

      values <- as.matrix(data)
      storage.mode(values) <- "double"

      zeros <- which(values == 0)
      values[zeros] <- stats::runif(length(zeros), 0, 1e-9)

      data_pn <- values
      for (batch in unique(bioProject)) {
        batch_rows <- which(bioProject == batch)
        control_rows <- batch_rows[phenotype_values[batch_rows] == control_level]
        if (length(control_rows) < 2) {
          stop("Batch '", batch, "' has fewer than two '", control_level, "' samples, so no ",
               "reference distribution can be built for it. Percentile normalisation needs ",
               "control samples in every batch.")
        }
        for (j in seq_len(ncol(values))) {
          data_pn[batch_rows, j] <- percentile_of_score(values[control_rows, j],
                                                        values[batch_rows, j])
        }
      }

      colnames(data_pn) <- colnames(data)
      rownames(data_pn) <- rownames(data)

      #Saving the data...
      data_pn <- as.data.frame(data_pn)
      data_pn[[sample_id_column]] <- run_column  # Add back the "run" column
      data_pn[[study_name]] <- study_name_column
      data_pn[[factor_of_interest]] <- factor_of_interest_column

      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_pn-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      write_csv(data_pn, output_file)
      print("PN finished.")
      
    }, error = function(e) {
      # General error for unexpected issues
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})