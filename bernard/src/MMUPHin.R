suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(MMUPHin)
  library(readr)
  library(jsonlite)
  batch_correction_method <- "MMUPHin"

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
        stop("MMUPHin requires at least two ", study_name, " levels to run.")
      }

      raw_abd <- as.matrix(data)
      raw_abd[raw_abd < 0] <- 0
      row_sums <- rowSums(raw_abd)
      row_sums[row_sums == 0] <- 1
      tss <- raw_abd / row_sums
      feature_abd <- t(tss)

      meta_mmuphin <- data.frame(
        batch = factor(bioProject),
        factor_of_interest = diagnosis,
        row.names = colnames(feature_abd)
      )

      run_adjust_batch <- function(covariates) {
        adjust_batch(
          feature_abd = feature_abd,
          batch = "batch",
          covariates = covariates,
          data = meta_mmuphin,
          control = list(verbose = FALSE, diagnostic_plot = NULL)
        )
      }
      fit <- tryCatch(
        run_adjust_batch("factor_of_interest"),
        error = function(e) {
          if (!grepl("confounded", conditionMessage(e))) stop(e)
          cat(factor_of_interest, " is confounded with ", study_name, " (", conditionMessage(e),
              "); correcting without it as a covariate.\n", sep = "")
          run_adjust_batch(NULL)
        })
      corrected_data <- as.data.frame(t(fit$feature_abd_adj))

      corrected_data[[sample_id_column]] <- run_column
      corrected_data[[study_name]] <- study_name_column
      corrected_data[[factor_of_interest]] <- factor_of_interest_column

      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_MMUPHin-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      write_csv(corrected_data, output_file)
      print("MMUPHin finished.")

    }, error = function(e) {
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})
