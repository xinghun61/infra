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
        return t.TestName == this.$.editExpectationForm.expectation.TestName;
      }, this);
      Object.assign(expectation, evt.detail.newValue);

      let formData = {
        TestName: expectation.TestName,
        Expectations: expectation.Expectations,
        Modifiers: expectation.Modifiers,
        Bugs: expectation.Bugs,
        XsrfToken: window.xsrfToken,
      };

      fetch('/api/v1/testexpectation', {
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify(formData),
      }).then((resp) => {
        if (resp.ok) {
          this.$.editDialog.toggle();
        } else {
          // TODO: indicate failure in the dialog.
          window.console.error('Non-OK response for updating expectation', resp);
        }
      }).catch((error) => {
        window.console.error('Failed to update layout expectation: ', error);
        this.$.editDialog.toggle();
      });
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
