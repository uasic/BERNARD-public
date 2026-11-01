options(repos = c(CRAN = "https://cloud.r-project.org"))
# Function to check if a package is installed
is_installed <- function(pkg) {
  pkg %in% rownames(installed.packages())
}

# Install required packages from CRAN with specific versions only if not installed
if (!is_installed("remotes")) install.packages("remotes")

if (!is_installed("gdtools")) install.packages("gdtools")

#remove.packages("sf")
#install.packages("sf")
#remove.packages("terra")
if (!is_installed("raster")) install.packages("raster", dependencies = TRUE)

#if (!is_installed("BiocManager")) install.packages("https://cran.r-project.org/src/contrib/BiocManager_1.30.25.tar.gz", repos=NULL, type="source")
BiocManager::install(version = "3.21", ask = FALSE)

if (!is_installed("devtools")) install.packages("devtools")

# Install specific versions only if not installed
if (!is_installed("doParallel")) remotes::install_version("doParallel", version = "1.0.17")
if (!is_installed("foreach")) remotes::install_version("foreach", version = "1.5.2")
if (!is_installed("iterators")) remotes::install_version("iterators", version = "1.0.14")
if (!is_installed("readr")) remotes::install_version("readr", version = "2.1.5")
if (!is_installed("pheatmap")) remotes::install_version("pheatmap", version = "1.0.12")
if (!is_installed("vegan")) remotes::install_version("vegan", version = "2.6-10")
if (!is_installed("gridExtra")) remotes::install_version("gridExtra", version = "2.3")

# Install GitHub package only if not installed
if (!is_installed("ConQuR")) devtools::install_github("wdl2459/ConQuR")

# MetaDICT's CRAN/Bioconductor dependencies (RANN, igraph, vegan, edgeR, ecodist,
# ggplot2, viridis, ggpubr, ape, cluster, matrixStats) are resolved automatically
# by install_github, except edgeR which is installed explicitly below via
# BiocManager since it lives on Bioconductor, not CRAN.
if (!is_installed("MetaDICT")) devtools::install_github("BoYuan07/MetaDICT")

# FAbatch.R dependency (model-based batch adjustment). bapred only lists
# affyPLM/affy as Suggests, so install.packages() won't pull them in
# automatically even though loading bapred requires them; they're added to
# bioc_pkgs below to guarantee they're present.
if (!is_installed("bapred")) install.packages("bapred")

# RUVIIINB.R dependencies: DescTools (Winsorize) is on CRAN, ruvIIInb is
# GitHub-only. Matrix ships with base R.
if (!is_installed("DescTools")) install.packages("DescTools")
if (!is_installed("ruvIIInb")) devtools::install_github("limfuxing/ruvIIInb")

# DEBIASM.R bridges to Python via reticulate; the Python-side `debiasm`
# package itself is optional and installed separately (see
# requirements/requirements-debias.txt) because it pulls in a large
# PyTorch stack.
if (!is_installed("reticulate")) install.packages("reticulate")

# Install Bioconductor packages only if not installed
bioc_pkgs <- c("BiocParallel", "MBECS", "preprocessCore", "phyloseq",
               "ruv", "sva", "limma", "Biobase", "TreeSummarizedExperiment",
               "PLSDAbatch", "mixOmics", "edgeR", "MMUPHin", "affyPLM", "affy")

for (pkg in bioc_pkgs) {
  if (!is_installed(pkg)) BiocManager::install(pkg, ask=FALSE)
}
