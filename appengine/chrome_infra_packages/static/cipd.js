/**
 * @fileoverview Common functions needed by cipd frontend components.
 */

var cipd = cipd || {};

(function() {

'use strict';

cipd.apiRoot = [
  window.location.protocol, '//', window.location.host, '/_ah/api'
].join('');

cipd.directoryLink = function(path) {
  return '#/?path=' + path;
};

cipd.packageLink = function(path) {
  return '#/pkg?path=' + path;
};

cipd.suffix = function(path) {
  return path.split('/').pop();
};

})();
