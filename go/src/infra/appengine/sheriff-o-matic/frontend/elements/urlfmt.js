(function(window) {
  'use strict';
  var urlFmt = window.urlFmt || {};

  const archivePrefix =
      'https://storage.googleapis.com/chromium-layout-test-archives/';

  urlFmt.layoutTestBase = function(builderName, buildNumber) {
    let builderPath = builderName.replace(/[ .()]/g, '_');
    return archivePrefix + `${builderPath}/${buildNumber}/layout-test-results`;
  };

  urlFmt.layoutTest = function(builderName, buildNumber, testName) {
    // Remove the file extension.
    let testBase = testName.substr(0, testName.lastIndexOf('.')) || testName;
    let basePath = urlFmt.layoutTestBase(builderName, buildNumber);

    return `${basePath}/${testBase}`;
  };

  urlFmt.layoutTestAll = function(builderName, buildNumber) {
    let basePath = urlFmt.layoutTestBase(builderName, buildNumber);
    return `${basePath}/results.html`;
  };

  window.urlFmt = urlFmt;
})(window);
