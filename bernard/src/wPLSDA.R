suppressPackageStartupMessages({
  args <- commandArgs(trailingOnly = TRUE)

  library(pheatmap)
  library(vegan)
  library(gridExtra)
  library(readr)
  library(mixOmics)
  library(Biobase)
  library(TreeSummarizedExperiment)
  library(PLSDAbatch)
  library(jsonlite)
  batch_correction_method <- "wPLSDA"
  
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
  print(csv_inputs)
  
  # Load metadata
  metadata_file = file.path(raw_data, "covariates.txt")
  metadata_columns <- readLines(metadata_file, warn=FALSE)
  print(metadata_columns)
  
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
  
  choose_number_of_components <- function(explained_variance, threshold = 0.999) {
    explained_variance <- as.numeric(explained_variance)
    explained_variance <- explained_variance[!is.na(explained_variance)]
    if (length(explained_variance) == 0) return(1)
    chosen <- which(cumsum(explained_variance) >= threshold)[1]
    if (is.na(chosen)) chosen <- length(explained_variance)
    max(1, chosen)
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
    
    tryCatch(
      {
        #Load data
        print("Loading data...")
        full_file_path <- file.path(input_folder, file)
        data <- read_csv(full_file_path, show_col_types = FALSE)
        data <- as.data.frame(data)
        cat("Processing file: ", file)
        
        # Rename "Unnamed: 0" to the sample_id_column (e.g., "run") if it exists
        print("Updating data...")
        if ("Unnamed: 0" %in% colnames(data)) {
          colnames(data)[colnames(data) == "Unnamed: 0"] <- sample_id_column
        }
        data <- data[, !(names(data) %in% metadata_columns)]
        
        run_column <- data[[sample_id_column]]
        study_name_column <- data[[study_name]]
        factor_of_interest_column <- data[[factor_of_interest]]
        
        metadata_data <- metadata_columns
        
        print("Updating data...")
        rownames(data) <- data[[sample_id_column]]
        data[[sample_id_column]] <- NULL 
        
        #Remove unnecessary metadata
        data <- data[, !(names(data) %in% metadata_columns)]
        data$...1 <- NULL
        
        data[[factor_of_interest]][data[[factor_of_interest]] == 0] <- "unknown"
        data[[factor_of_interest]][data[[factor_of_interest]] == "0"] <- "unknown"
        
        print("Defining batch and phenotype...")
        ad.batch = factor(data[[study_name]],levels = unique(data[[study_name]]))
        ad.phenotype = as.factor(data[[factor_of_interest]])
        
        data[[study_name]] <- NULL
        data[[factor_of_interest]] <- NULL
        
        print("Logratio transformation")
        data <- as.matrix(data) #For logratio.transfo() you need numeric matrix
        ad.clr <- logratio.transfo(X = data, logratio = 'CLR', offset = log_offset(data)) 
        class(ad.clr) = 'matrix'
  
        ncomp.trt <- max(1, nlevels(ad.phenotype) - 1)
        ad.phenotype.tune <- plsda(X = ad.clr, Y = ad.phenotype, ncomp = ncomp.trt)
        # % PLS components (new predictors)
        print("Proportion of variance explained with components:")
        print(ad.phenotype.tune$prop_expl_var)

        print("Estimating the number of batch components")
        ncomp.bat.max <- max(1, min(10, nlevels(ad.batch)))
        ad.batch.tune <- PLSDA_batch(X = ad.clr,
                                     Y.trt = ad.phenotype, Y.bat = ad.batch,
                                     ncomp.trt = ncomp.trt, ncomp.bat = ncomp.bat.max, balance = FALSE)
        print("Displays the percentage of variance in Y.bat (the batch variable) explained by each batch component.")
        print(ad.batch.tune$explained_variance.bat)

        ncomp.bat <- choose_number_of_components(ad.batch.tune$explained_variance.bat$Y)
        cat("Number of batch components used: ", ncomp.bat, " of ", ncomp.bat.max, "\n", sep = "")

        print("Batch correction")
        ad.PLSDA_batch.res <- PLSDA_batch(X = ad.clr,
                                          Y.trt = ad.phenotype, Y.bat = ad.batch,
                                          ncomp.trt = ncomp.trt, ncomp.bat = ncomp.bat,
                                          balance = FALSE)
        ad.wPLSDA_batch <- ad.PLSDA_batch.res$X.nobatch
        ad.wPLSDA_batch <- cbind(setNames(data.frame(rownames(ad.wPLSDA_batch)), sample_id_column), ad.wPLSDA_batch)
  
        print("Saving corrected data...")
        ad.wPLSDA_batch <- as.data.frame(ad.wPLSDA_batch)
        ad.wPLSDA_batch[[sample_id_column]] <- run_column  # Add back the "run" column
        ad.wPLSDA_batch[[study_name]] <- study_name_column
        ad.wPLSDA_batch[[factor_of_interest]] <- factor_of_interest_column
        # Generate the base name of the file (without path and extension)
        base_name <- tools::file_path_sans_ext(basename(file))  # Extract the base name of the input file
        # Construct the custom output file name with "wPLSDA" string
        output_file_name <- paste0(base_name, "_wPLSDA-tmp.csv")
        # Create the full output file path by combining the output folder and the custom file name
        output_file <- file.path(output_folder, output_file_name)
        # Save the corrected data to the output file
        write_csv(ad.wPLSDA_batch, output_file)
        print("wPLSDA finished.")
      } , error = function(e) {
        # General error for unexpected issues
        message("An unexpected error occurred with file: ", file, "\nError: ", e)
      }
    )
  }
})