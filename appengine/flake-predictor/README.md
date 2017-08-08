# Overview

flake-predictor is a tool that uses machine learning to predict whether
or not a given test failure on CQ or Waterfall was the result of a flakey test.
The goal is to save time for developers by letting them know which of their test
failures are likely flakes so that they can focus their time on fixing the true
test failures. Broadly, the app collects data from recipes, labels the data
using FindIt, and then uses the labeled data to train a TensorFlow model which
can serve predictions.

# How to run flake-predictor tests

flake-predictor uses apache_beam, which is not on the mac/windows build bots
yet. For this reason, flake-predictor tests are not run by CQ. To run the
tests locally, use this command:

`./test.py test appengine/flake-predictor
    --coveragerc=appengine/flake-predictor/.coveragerc-hidden`

