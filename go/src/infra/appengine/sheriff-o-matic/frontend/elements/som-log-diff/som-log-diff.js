(function() {
  'use strict';

  Polymer({
    is:'som-log-diff',
    properties: {
      tree: {
        value: 'chromium',
        notify: true,
      },
      _diffLines: {
        type: Array,
        default: function () {
        return [];
        },
      },
      key: {
        type: String,
      },
      master: {
        type: String,
        computed: '_computeMaster(key)',
      },
      builder: {
        type: String,
        computed: '_computeBuilder(key)',
      },
      buildNum1: {
        type: String,
        computed: '_computeBuildNum1(key)',
      },
      buildNum2: {
        type: String,
        computed: '_computeBuildNum2(key)',
      },
      url: {
        type: String,
        computed: '_computeURL(key)',
      },
    },

    _computeMaster: function(key) {
      let params = key.split('/');
      return params[0];
    },

    _computeBuilder: function(key) {
      let params = key.split('/');
      return params[1];
    },

    _computeBuildNum1: function(key) {
      let params = key.split('/');
      return params[2];
    },

    _computeBuildNum2: function(key) {
      let params = key.split('/');
      return params[3];
    },

    _isDel: function(delta) {
      return delta === 1;
    },

    _isCommon: function(delta) {
      return delta === 0;
    },

    _isAdd: function (delta) {
      return delta === 2;
    },

    _computeURL: function(key) {
      return "/api/v1/logdiff/" + key;
    },
  });
})();
