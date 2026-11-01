suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(DescTools)
  library(ruvIIInb)
  library(Matrix)
  library(readr)
  library(jsonlite)
  batch_correction_method <- "RUVIIINB"

  set.seed(42)

  patch_DescTools_Winsorize <- function() {
    orig <- getFromNamespace("Winsorize", "DescTools")
    compat <- function(x, probs = c(0.05, 0.95), na.rm = FALSE, ...) {
      orig_sig <- names(formals(orig))
      if (all(c("probs", "na.rm") %in% orig_sig)) {
        return(orig(x, probs = probs, na.rm = na.rm, ...))
      }
      qs <- stats::quantile(x, probs = probs, na.rm = na.rm, names = FALSE, type = 7)
      lo <- qs[1]; hi <- qs[2]
      x[x < lo] <- lo; x[x > hi] <- hi
      x
    }
    utils::assignInNamespace("Winsorize", compat, ns = "DescTools")
    invisible(TRUE)
  }
  patch_DescTools_Winsorize()

  Sys.setenv(OMP_NUM_THREADS = "1", MKL_NUM_THREADS = "1", OPENBLAS_NUM_THREADS = "1")

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
        stop("RUV-III-NB requires at least two ", study_name, " levels to run.")
      }

      values <- as.matrix(data)
      storage.mode(values) <- "double"
      values[!is.finite(values) | values < 0] <- 0
      is_integer_valued <- all(abs(values - round(values)) < 1e-8)
      if (!is_integer_valued && max(rowSums(values)) <= 100.5) {
        cat("Relative abundances detected; converting to pseudo counts (1e5 per sample).\n")
        library_size <- rowSums(values)
        library_size[library_size == 0] <- 1
        values <- values / library_size * 1e5
      }
      Y <- t(round(values))
      storage.mode(Y) <- "integer"

      batch_factor <- factor(bioProject)

      phenotype <- factor(diagnosis)
      if (nlevels(phenotype) < 2) {
        stop("RUV-III-NB needs at least two ", factor_of_interest, " groups to build a replicate matrix.")
      }
      if (any(table(phenotype) < 2)) {
        stop("RUV-III-NB needs at least two samples in every ", factor_of_interest,
             " group to use them as pseudo replicates.")
      }
      M <- model.matrix(~ 0 + phenotype)
      rownames(M) <- colnames(Y)

      library_size <- colSums(Y)
      library_size[library_size == 0] <- 1
      log_norm <- log1p(t(Y) / library_size * stats::median(library_size))
      control_p_values <- apply(log_norm, 2, function(feature_values) {
        if (stats::sd(feature_values) == 0) return(1)
        tryCatch(stats::anova(stats::lm(feature_values ~ phenotype))[["Pr(>F)"]][1],
                 error = function(e) 1)
      })
      control_p_values[is.na(control_p_values)] <- 0
      ctl_names <- rownames(Y)[control_p_values > 0.05]
      if (length(ctl_names) < 2) {
        n_fallback <- max(2, ceiling(nrow(Y) / 2))
        ctl_names <- rownames(Y)[order(control_p_values, decreasing = TRUE)][seq_len(n_fallback)]
        cat("Fewer than two features show no association with ", factor_of_interest,
            "; using the ", n_fallback, " least associated features as controls instead.\n", sep = "")
      }
      cat("Pseudo negative controls: ", length(ctl_names), " of ", nrow(Y), " features\n", sep = "")

      k_val <- max(1, min(nlevels(batch_factor) - 1, length(ctl_names) - 1))
      cat("Number of removed unwanted factors (k): ", k_val, "\n", sep = "")

      fit <- ruvIIInb::ruvIII.nb(
        Y = as.matrix(Y),
        M = as.matrix(M),
        ctl = ctl_names,
        k = k_val,
        batch = as.numeric(batch_factor),
        ncores = 1L,
        use.pseudosample = FALSE,
        batch.disp = FALSE,
        zeroinf = rep(FALSE, ncol(Y))
      )
      Yfit <- as.matrix(fit$counts)
      Wa <- as.matrix(Matrix::tcrossprod(fit$a, fit$W))
      if (!identical(dim(Wa), dim(Yfit))) {
        stop("the unwanted-variation term came out ", nrow(Wa), "x", ncol(Wa),
             " against a fitted count matrix of ", nrow(Yfit), "x", ncol(Yfit), ".")
      }
      dimnames(Wa) <- dimnames(Yfit)
      if (!is.null(dim(fit$pi0))) {
        mu <- exp(Wa) * (1 - fit$pi0[, as.numeric(batch_factor), drop = FALSE])
      } else {
        mu <- exp(Wa)
      }
      adjusted_fit <- log(Yfit / mu + 1)

      adjusted <- matrix(0, nrow = nrow(Y), ncol = ncol(Y), dimnames = dimnames(Y))
      adjusted[rownames(adjusted_fit), colnames(adjusted_fit)] <- adjusted_fit
      corrected_data <- as.data.frame(t(adjusted))

      corrected_data[[sample_id_column]] <- run_column
      corrected_data[[study_name]] <- study_name_column
      corrected_data[[factor_of_interest]] <- factor_of_interest_column

      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_RUVIIINB-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      write_csv(corrected_data, output_file)
      print("RUV-III-NB finished.")

    }, error = function(e) {
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})
