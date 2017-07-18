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
        computed: 'computeMaster(key)',
      },
      builder: {
        type: String,
        computed: 'computeBuilder(key)',
      },
      buildNum1: {
        type: String,
        computed: 'computeBuildNum1(key)',
      },
      buildNum2: {
        type: String,
        computed: 'computeBuildNum2(key)',
      },
      url: {
        type: String,
        computed: 'computeURL(key)',
      },
    },

    computeMaster: function(key) {
      let params = key.split('/');
      return params[0];
    },

    computeBuilder: function(key) {
      let params = key.split('/');
      return params[1];
    },

    computeBuildNum1: function(key) {
      let params = key.split('/');
      return params[2];
    },

    computeBuildNum2: function(key) {
      let params = key.split('/');
      return params[3];
    },

    isDel: function(delta) {
      return delta === 1;
    },

    isCommon: function(delta) {
      return delta === 0;
    },

    isAdd: function (delta) {
      return delta === 2;
    },

    _computeAdd: function(payload) {
      return '+ ' + payload;
    },

    _computeDel: function(payload) {
      return '- ' + payload;
    },

    computeURL: function(key) {
      return "/api/v1/logdiff/" + key;
    },
  });
})();
