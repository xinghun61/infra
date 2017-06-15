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
      Promise.all(promises).then(
          (response) => {
            this._testExpectationsLoaded = true;
          },
          (error) => {
            console.error(error);
          });
    },

    _onActiveItemChanged: function(evt) {
      this.$.grid.expandedItems = [evt.detail.value];
    },

    _showTestExpectationsLoading: function(testExpectationsLoaded, error) {
      return !testExpectationsLoaded && this._haveNoErrors(error);
    },

    _haveNoErrors: function(error) {
      return !error;
    },

    _shortFileName: function(fn) {
      if (!fn)
        return '';
      let parts = fn.split('/');
      return parts.pop();
    },

    _onCreateChangeCL: function(evt) {
      let expectation = this._testExpectationsJson.find((t) => {
        // TODO: test if this filtering is necessary due to references.
        return t.TestName == this.$.editExpectationForm.expectation.TestName;
      }, this);
      Object.assign(expectation, evt.detail.newValue);
      // TODO: activity indicator?
      this.$.editDialog.toggle();
    },

    _onCancelChangeCL: function(evt) {
      this.$.editDialog.toggle();
    },

    _onStartEdit: function(evt) {
      let expectation = this._testExpectationsJson.find((t) => {
        return t.TestName == evt.target.value;
      });
      this.$.editExpectationForm.set('expectation', expectation);
      this.$.editDialog.toggle();
    },
  });
})();
