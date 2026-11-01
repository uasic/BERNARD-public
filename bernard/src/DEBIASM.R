suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(reticulate)
  library(readr)
  library(jsonlite)
  batch_correction_method <- "DEBIASM"

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

  py <- Sys.getenv("RETICULATE_PYTHON")
  project_venv <- ".venv"
  if (nzchar(py)) {
    reticulate::use_python(py, required = TRUE)
  } else if (dir.exists(project_venv)) {
    reticulate::use_virtualenv(normalizePath(project_venv, winslash = "/", mustWork = TRUE), required = TRUE)
  } else {
    cand <- Sys.which(c("python3", "python"))
    cand <- unname(cand[cand != ""])
    if (length(cand) > 0) py <- cand[[1]]
    if (!nzchar(py)) py <- "python"
    reticulate::use_python(py, required = TRUE)
  }

  if (!py_module_available("numpy") || !py_module_available("debiasm")) {
    stop("DEBIAS-M requires the Python modules numpy and debiasm in the ",
         "configured Python environment. Install requirements/requirements-debias.txt first.")
  }

  np <- import("numpy", delay_load = TRUE)
  debiasm <- import("debiasm", delay_load = TRUE)
  pytorch_lightning <- import("pytorch_lightning", delay_load = TRUE)

  reticulate::py_run_string("
import inspect
import pytorch_lightning as _pl
if 'checkpoint_callback' not in inspect.signature(_pl.Trainer.__init__).parameters \\
        and not getattr(_pl.Trainer, '_bernard_compat', False):
    class _CompatTrainer(_pl.Trainer):
        _bernard_compat = True
        def __init__(self, *args, checkpoint_callback=None, weights_summary='unset',
                     progress_bar_refresh_rate=None, **kwargs):
            if checkpoint_callback is not None:
                kwargs.setdefault('enable_checkpointing', bool(checkpoint_callback))
            if weights_summary != 'unset':
                kwargs.setdefault('enable_model_summary', weights_summary is not None)
            if progress_bar_refresh_rate is not None:
                kwargs.setdefault('enable_progress_bar', progress_bar_refresh_rate > 0)
            super().__init__(*args, **kwargs)
    _pl.Trainer = _CompatTrainer
")

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
    pytorch_lightning$seed_everything(dataset_seed)

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
        stop("DEBIAS-M requires at least two ", study_name, " levels to run.")
      }

      X_cnt <- as_count_matrix(as.matrix(data))

      y_all <- diagnosis
      is_num <- is.numeric(y_all)
      uniq_vals <- unique(y_all[!is.na(y_all)])
      is_integerish <- is_num && all(abs(uniq_vals - round(uniq_vals)) < 1e-8)
      use_classifier <- (!is_num) || (is_integerish && length(uniq_vals) <= 10)

      b0 <- as.integer(factor(bioProject)) - 1L
      X_with_batch <- cbind(b0, X_cnt)

      uniq_b <- sort(unique(b0))
      if (length(uniq_b) >= 2) {
        val_batch <- tail(uniq_b, 1)
        val_inds <- (b0 == val_batch)
      } else {
        val_inds <- rep(FALSE, nrow(X_with_batch))
        val_inds[sample.int(nrow(X_with_batch), max(1L, floor(0.2 * nrow(X_with_batch))))] <- TRUE
      }
      if (sum(!val_inds) < 2) {
        val_inds <- rep(FALSE, nrow(X_with_batch))
        val_inds[sample.int(nrow(X_with_batch), max(1L, floor(0.2 * nrow(X_with_batch))))] <- TRUE
      }

      X_train_R <- X_with_batch[!val_inds, , drop = FALSE]
      X_val_R <- X_with_batch[val_inds, , drop = FALSE]
      y_train_R <- y_all[!val_inds]

      if (use_classifier && length(unique(stats::na.omit(y_train_R))) < 2 && length(unique(y_all)) >= 2) {
        val_inds <- rep(FALSE, nrow(X_with_batch))
        val_inds[sample.int(nrow(X_with_batch), max(1L, floor(0.2 * nrow(X_with_batch))))] <- TRUE
        X_train_R <- X_with_batch[!val_inds, , drop = FALSE]
        X_val_R <- X_with_batch[val_inds, , drop = FALSE]
        y_train_R <- y_all[!val_inds]
      }

      X_train <- np$array(X_train_R, dtype = "int64")
      X_val <- np$array(X_val_R, dtype = "int64")
      X_full <- np$array(X_with_batch, dtype = "int64")

      if (use_classifier) {
        yf <- as.factor(y_train_R)
        if (anyNA(yf)) { tab <- sort(table(yf), decreasing = TRUE); yf[is.na(yf)] <- names(tab)[1] }
        y_train <- np$array(as.integer(yf) - 1L, dtype = "int64")
        model <- debiasm$DebiasMClassifier(x_val = X_val)
      } else {
        yr <- as.numeric(y_train_R)
        if (anyNA(yr)) yr[is.na(yr)] <- mean(yr, na.rm = TRUE)
        y_train <- np$array(yr, dtype = "float32")
        model <- debiasm$DebiasMRegressor(x_val = X_val)
      }

      model$fit(X_train, y_train)
      X_debiased <- model$transform(X_full)
      Xd <- tryCatch(
        as.matrix(py_to_r(X_debiased)),
        error = function(e) as.matrix(X_debiased)
      )

      p_full <- ncol(X_with_batch)
      p_feat <- ncol(X_cnt)
      if (nrow(Xd) == p_full && ncol(Xd) == nrow(X_with_batch)) Xd <- t(Xd)

      if (ncol(Xd) == p_full) {
        out_counts <- Xd[, -1, drop = FALSE]
      } else if (ncol(Xd) == p_feat) {
        out_counts <- Xd
      } else {
        stop("DEBIAS-M: unexpected transform shape (got ", ncol(Xd),
             " columns; expected ", p_feat, " or ", p_full, ").")
      }
      dimnames(out_counts) <- dimnames(X_cnt)
      corrected_data <- as.data.frame(out_counts)

      corrected_data[[sample_id_column]] <- run_column
      corrected_data[[study_name]] <- study_name_column
      corrected_data[[factor_of_interest]] <- factor_of_interest_column

      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_DEBIASM-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      write_csv(corrected_data, output_file)
      print("DEBIAS-M finished.")

    }, error = function(e) {
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})
