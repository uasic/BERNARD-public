suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(bapred)
  library(mixOmics)
  library(readr)
  library(jsonlite)
  batch_correction_method <- "FAbatch"

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
        stop("FAbatch requires at least two ", study_name, " levels to run.")
      }
      if (length(unique(diagnosis)) != 2) {
        stop("FAbatch requires a binary ", factor_of_interest, " (found ", length(unique(diagnosis)), " levels).")
      }

      X <- as.matrix(data)
      X_clr <- logratio.transfo(X = X, logratio = "CLR", offset = log_offset(X))
      class(X_clr) <- "matrix"

      y <- factor(diagnosis, levels = sort(unique(diagnosis)))
      batch <- factor(bioProject)

      v <- apply(X_clr, 2, var)
      keep_var <- is.finite(v) & v > 1e-12
      if (!any(keep_var)) {
        stop("FAbatch: all features have ~zero variance after CLR transformation.")
      }
      Xk <- X_clr[, keep_var, drop = FALSE]
      max_batch_size <- max(table(batch))
      if (ncol(Xk) <= max_batch_size) {
        stop("FAbatch needs more variable features than the largest ", study_name, " group (have ", ncol(Xk), ", need > ", max_batch_size, ").")
      }
      Xz <- scale(Xk, center = TRUE, scale = TRUE)

      fa_out <- NULL
      for (max_factors in c(12L, 8L, 6L, 4L)) {
        fa_out <- tryCatch(
          fabatch(
            x = Xz, y = y, batch = batch,
            nbf = NULL, minerr = 1e-6, probcrossbatch = TRUE, maxiter = 100, maxnbf = max_factors
          ),
          error = function(e) {
            if (!grepl("singular", conditionMessage(e)) || max_factors == 4L) stop(e)
            cat("fabatch() with up to ", max_factors, " factors per batch: ", conditionMessage(e),
                "; retrying with fewer.\n", sep = "")
            NULL
          })
        if (!is.null(fa_out)) break
      }
      cat("Latent factors per batch: ", paste(fa_out$nbfvec, collapse = ", "), "\n", sep = "")

      m <- attr(Xz, "scaled:center"); s <- attr(Xz, "scaled:scale")
      Xadj_sub <- sweep(fa_out$xadj, 2, s, `*`)
      Xadj_sub <- sweep(Xadj_sub, 2, m, `+`)
      X_clr[, colnames(Xk)] <- Xadj_sub
      corrected_data <- as.data.frame(X_clr)

      corrected_data[[sample_id_column]] <- run_column
      corrected_data[[study_name]] <- study_name_column
      corrected_data[[factor_of_interest]] <- factor_of_interest_column

      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_FAbatch-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      write_csv(corrected_data, output_file)
      print("FAbatch finished.")

    }, error = function(e) {
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})
