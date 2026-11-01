bernard_folder  = None
raw_data_folder = None

run_permdisp          = True
permdisp_permutations = 999
permdisp_test         = 'median'

evaluation_space = 'zscore-euclidean'

roc_curves = {}

batch_dissimilarity = {}
feature_r2_distributions = {}

run_stability      = True
stability_resamples = 100
stability_fraction  = 0.8

run_auroc = True

outlier_contamination = 0.05

run_neighbourhood_metrics = True
neighbourhood_k           = 30

random_seed             = 42
permanova_permutations  = 999
significance_alpha      = 0.05
kbet_alpha              = 0.05
auroc_trees             = 200
auroc_folds             = 5
pvca_variance_threshold = 0.8
pvca_max_components     = 10
tsne_perplexity         = 0.0
figure_dpi              = 300
