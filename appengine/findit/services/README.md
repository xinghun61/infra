This code directory is for the core logic of analysis. Code under this directory
should know nothing about pipeline flows. For pipeline flows, please use
[pipelines](../pipelines) instead.

There are three sub-directories for three different types of failures. But
modules containing shared logic could live in this directory as well.
* [Compile failures](compile_failure) is to analyze compile step failures on
  the Chromium Waterfall.
* [Flake failures](flake_failure) is to analyze flaky test failures detected on
  the Chromium Waterfall or Commit Queue.
* [Test failures](test_failure) is to analyze reliable test failures detected on
  the Chromium Waterfall.

For reliable or flaky test failures, currently only Swarmed gtests and Android
instrumentation tests are supported.
