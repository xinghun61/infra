/**
 * @fileoverview Common functions needed by cipd frontend components.
 */

var cipd = cipd || {};

(function() {

'use strict';

// Override this if you want to test against another instance (e.g. to prod from
// dev or local).
// TODO(estaab): Make this smarter by selecting document.location if not running
// a local dev instance.
cipd.apiRoot = 'https://chrome-infra-packages.appspot.com/_ah/api';

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
