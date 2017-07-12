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
      master: {
        type: String,
        notify: true,
      },
      builder: {
        type: String,
        notify: true,
      },
      buildNum1: {
        type: String,
        notify: true,
      },
      buildNum2: {
        type: String,
        notify: true,
      },
      url: {
        computed: 'computeURL(master, builder, buildNum1, buildNum2)',
      },
      isComplete: {
        type: Boolean,
        value: true,
      },
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

    computeURL: function(master, builder, buildNum1, buildNum2) {
      return "/api/v1/logdiff/" + master + '/' + builder + '/' + buildNum1 + '/' + buildNum2;
    },

    stillLoading: function() {
      this.isComplete = false;
      return;
    },
  });
})();
