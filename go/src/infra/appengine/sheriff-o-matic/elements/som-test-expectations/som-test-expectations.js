(function() {
  'use strict';

  Polymer({
    is: 'som-test-expectations',

    properties: {
      _testExpectationsJson: {
        type: Array,
        value: [],
      },
      _testExpectationsJsonError: {
        type: Object,
        value: null,
      },
      _testExpectationsLoaded: {
        type: Boolean,
        value: false,
      },
    },

    ready: function() {
      this.refresh();
    },

    refresh: function() {
      let promises = [this.$.testExpectationsAjax.generateRequest().completes];
      Promise.all(promises).then((reponse) => {
        this._testExpectationsLoaded = true;
      });
    },

    _showTestExpectationsLoading: function(testExpectationsLoaded, error) {
      return !testExpectationsLoaded && this._haveNoErrors(error);
    },

    _haveNoErrors: function(error) {
      return !error;
    },

    _shortFileName: function(fn) {
      if (!fn) return '';
      let parts = fn.split('/');
      return parts.pop();
    },
  });
})();
