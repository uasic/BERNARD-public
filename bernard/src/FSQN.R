suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(readr)
  library(jsonlite)
  batch_correction_method <- "FSQN"

  set.seed(42)

  bernard_folder <- args[1]
  print(bernard_folder)

  input_folder <- file.path(bernard_folder, "outputs", "cleaned")
  output_folder <- file.path(bernard_folder, "outputs", "corrected")
  raw_data <- file.path(bernard_folder, "raw-data")

  csv_inputs <- list.files(path = input_folder, pattern = "\\.csv$", full.names = FALSE)
  csv_inputs <- setdiff(csv_inputs, "metadata.csv")
  csv_inputs <- csv_inputs[order(file.info(file.path(input_folder, csv_inputs))$size,
                                 na.last = TRUE)]

  metadata_file <- file.path(raw_data, "covariates.txt")
  metadata_columns <- readLines(metadata_file, warn=FALSE)

  config_file <- file.path(raw_data, "config.json")
  config <- fromJSON(config_file)
  study_name <- config$study_name
  factor_of_interest <- config$factor_of_interest
  sample_id_column <- config$sample_id_column

  if (!is.null(config$random_seed)) {
    set.seed(as.integer(config$random_seed))
  }

  quantile_normalize_by_feature <- function(X, Xref) {
    out <- X
    for (j in seq_len(ncol(X))) {
      target <- Xref[, j]
      target <- target[is.finite(target)]
      if (length(target) < 2L || !all(is.finite(X[, j]))) next
      out[, j] <- preprocessCore::normalize.quantiles.use.target(
        matrix(X[, j], ncol = 1), target = target, copy = TRUE)[, 1]
    }
    out
  }

  for (file in csv_inputs) {
    dataset_seed <- if (!is.null(config$random_seed)) as.integer(config$random_seed) else 42L
    set.seed(dataset_seed)

    tryCatch({
      cat("Processing file: ", file)
      full_file_path <- file.path(input_folder, file)
      data <- read_csv(full_file_path, show_col_types = FALSE)
      data <- as.data.frame(data)

      if ("Unnamed: 0" %in% colnames(data)) {
        colnames(data)[colnames(data) == "Unnamed: 0"] <- sample_id_column
      }
      run_column <- data[[sample_id_column]]
      study_name_column <- data[[study_name]]
      factor_of_interest_column <- data[[factor_of_interest]]

      rownames(data) <- data[[sample_id_column]]
      data[[sample_id_column]] <- NULL

      data <- data[, !(names(data) %in% metadata_columns)]
      data$...1 <- NULL

      bioProject <- data[[study_name]]
      diagnosis <- data[[factor_of_interest]]
      data[[study_name]] <- NULL
      data[[factor_of_interest]] <- NULL

      if (length(unique(bioProject)) < 2) {
        stop("FSQN requires at least two ", study_name, " levels to run.")
      }

      X <- as.matrix(data)
      storage.mode(X) <- "double"

      reference_batch <- sort(unique(as.character(bioProject)))[1]
      ref_mask <- bioProject == reference_batch
      if (sum(ref_mask) < 2) {
        stop("FSQN requires at least two samples in the reference ", study_name, " level (", reference_batch, ").")
      }
      Xref <- X[ref_mask, , drop = FALSE]

      corrected <- X
      for (batch in setdiff(unique(as.character(bioProject)), reference_batch)) {
        rows <- which(as.character(bioProject) == batch)
        corrected[rows, ] <- quantile_normalize_by_feature(X[rows, , drop = FALSE], Xref)
      }
      corrected_data <- as.data.frame(corrected)

      corrected_data[[sample_id_column]] <- run_column
      corrected_data[[study_name]] <- study_name_column
      corrected_data[[factor_of_interest]] <- factor_of_interest_column

      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_FSQN-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      write_csv(corrected_data, output_file)
      print("FSQN finished.")

    }, error = function(e) {
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})
