(function() {
  'use strict';

  const MAX_ATTEMPTS = 10;
  const CHROMIUM_PREFIX = "chromium%2Fsrc~master~";

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
      _changeListId: {
        type: String,
        value: '',
      },
      _statusMessage: {
        type: String,
        value: '',
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
          resp.json().then((data) => {
              this.$.editDialog.toggle();
              this.$.changeListStatusDialog.toggle();
              this._queuedRequestId = data.QueuedRequestID;
              this._errorMessage = '';
              this._statusMessage = '';
              this._pollCLStatus();
          });
        } else {
          // TODO: indicate failure in the dialog.
          window.console.error('Non-OK response for updating expectation', resp);
        }
      }).catch((error) => {
        window.console.error('Failed to update layout expectation: ', error);
        this.$.editDialog.toggle();
      });
    },

    _pollCLStatus: function(opt_attempt) {
      let attempt = opt_attempt || 1;
      // Commence polling to get the CL ID.
      fetch(`/api/v1/testexpectation/${this._queuedRequestId}`, {
          credentials: 'same-origin'
      }).then((resp) => {
        if (resp.ok) {
          resp.json().then((data) => {
            if (data.ChangeID != '') {
              this.$.changeListStatusDialog.toggle();
              this._changeListId = data.ChangeID;
              if (this._changeListId.startsWith(CHROMIUM_PREFIX)) {
                this._changeListId =
                    this._changeListId.substr(CHROMIUM_PREFIX.length);
              }
              this.$.changeListDialog.toggle();
            } else if (data.ErrorMessage != '') {
              this._errorMessage = data.ErrorMessage;
              this._statusMessage = '';
              this.$.progress.hidden = true;
              this._cancelPollingTask();
            } else if (attempt < MAX_ATTEMPTS) {
              let delay = attempt * attempt;
              this._statusMessage =
                  `Working... Checking again in ${delay} seconds.`;
              this.$.progress.hidden = false;
              attempt += 1;
              this._pollingTask = this.async(
                  this._pollCLStatus.bind(this, attempt),
                  delay * 1000);
            } else {
              this._statusMessage = 'Too many CL status fetch attempts. Giving up.';
            }
          });
        } else {
          this._statusMessage = 'Failed to get CL status: ' + error;
        }
      }).catch((error) => {
        this._statusMessage = 'Error trying to fetch cl status: ' + error;
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

    _cancelPollingTask: function(evt) {
      if (this._pollingTask) {
        this.cancelAsync(this._pollingTask);
      }
    },
  });
})();
