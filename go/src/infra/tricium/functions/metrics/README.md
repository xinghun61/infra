# Metrics

Tricium analyzer to check that metrics metadata are correctly formatted and contain all of the necessary information.

Currently, this analyzer can be used for [UMA histogram](https://chromium.googlesource.com/chromium/src.git/+/HEAD/tools/metrics/histograms/README.md) submissions.

For each histogram, this analyzer checks:
1. There are multiple owners, to avoid a single point of failure.
2. The first owner is an individual, not a team, so there is a clear primary point of contact.

Note: We assume that histograms.xml has been autoformatted (i.e. by running `python pretty_print.py` in the histograms directory, which is enforced by the presubmit tooling).
