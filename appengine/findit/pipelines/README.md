This code directory is for the pipeline flows. For core logic of analysis,
please use [services](../services) instead.

There are three sub-directories for three different analysis flows. Shared
pipeline flows should also live in this directory.
* [Compile failures](compile_failure) is for the flow to analyze compile step
  failures on Chromium Waterfall.
* [Flake failures](flake_failure) is for the flow to analyze flaky test failures
  detected on Chromium Waterfall or Commit Queue.
* [Test failures](test_failure) is for the flow to analyze reliable test
  failures detected on Chromium Waterfall.
