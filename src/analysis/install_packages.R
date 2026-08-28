# R packages for causal analysis
packages <- c(
  "fixest",       # DID, event study, panel FE
  "rdrobust",     # RDD
  "ivreg",        # IV regression
  "did",          # Callaway & Sant'Anna staggered DID
  "ggplot2",      # Visualization
  "dplyr",        # Data manipulation
  "readr",        # CSV reading
  "broom",        # Tidy regression output
  "sandwich",     # Robust standard errors
  "lmtest",       # Hypothesis testing
  "stargazer",    # Regression tables
  "rddensity"     # McCrary density test for RDD
)

for (pkg in packages) {
  if (!require(pkg, character.only = TRUE)) {
    install.packages(pkg, repos = "https://cloud.r-project.org")
  }
}

cat("All R packages installed.\n")
