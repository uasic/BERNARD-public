suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(MetaDICT)
  library(readr)
  library(jsonlite)
  batch_correction_method <- "MetaDICT"

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

  taxonomy_from_names <- function(feature_names) {
    parts <- strsplit(feature_names, "[;|]")
    depth <- lengths(parts)
    if (length(unique(depth)) != 1 || depth[1] < 2) return(NULL)
    if (!all(grepl("^[a-z]__", unlist(parts)))) return(NULL)
    taxonomy <- as.data.frame(do.call(rbind, parts), stringsAsFactors = FALSE)
    rownames(taxonomy) <- feature_names
    colnames(taxonomy) <- paste0("level_", seq_len(ncol(taxonomy)))
    taxonomy
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
        stop("MetaDICT requires at least two ", study_name, " levels to run.")
      }

      metadict_order <- unlist(lapply(unique(bioProject), function(b) which(bioProject == b)),
                               use.names = FALSE)
      data <- data[metadict_order, , drop = FALSE]
      bioProject <- bioProject[metadict_order]
      diagnosis <- diagnosis[metadict_order]

      count <- t(as_count_matrix(as.matrix(data)))
      storage.mode(count) <- "double"

      meta <- data.frame(
        batch = factor(bioProject),
        factor_of_interest = factor(diagnosis),
        row.names = colnames(count)
      )

      taxonomy <- taxonomy_from_names(rownames(count))
      if (!is.null(taxonomy)) {
        cat("Taxonomy read from the feature names (", ncol(taxonomy), " levels); MetaDICT ",
            "derives the taxa similarity from it.\n", sep = "")
        metadict_res <- MetaDICT(count = count, meta = meta, taxonomy = taxonomy,
                                 tax_level = colnames(taxonomy)[ncol(taxonomy)], verbose = FALSE)
      } else {
        cat("No taxonomy in the feature names; MetaDICT uses the distance between the ",
            "features' abundance profiles instead.\n", sep = "")
        dist_mat <- as.matrix(dist(count))
        metadict_res <- MetaDICT(count = count, meta = meta, distance_matrix = dist_mat, verbose = FALSE)
      }
      corrected_data <- as.data.frame(t(metadict_res$count))

      returned_ids <- rownames(corrected_data)
      if (is.null(returned_ids) || !setequal(returned_ids, as.character(run_column))) {
        stop("MetaDICT returned samples that cannot be matched to the input by name; ",
             "refusing to write a dataset whose metadata may be misaligned.")
      }
      corrected_data <- corrected_data[match(as.character(run_column), returned_ids), ,
                                       drop = FALSE]
      rownames(corrected_data) <- NULL

      corrected_data[[sample_id_column]] <- run_column
      corrected_data[[study_name]] <- study_name_column
      corrected_data[[factor_of_interest]] <- factor_of_interest_column

      base_name <- tools::file_path_sans_ext(basename(file))
      output_file_name <- paste0(base_name, "_MetaDICT-tmp.csv")
      output_file <- file.path(output_folder, output_file_name)
      write_csv(corrected_data, output_file)
      print("MetaDICT finished.")

    }, error = function(e) {
      message("An unexpected error occurred with file: ", file, "\nError: ", e)
    })
  }
})
