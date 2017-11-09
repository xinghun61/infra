'use strict';

const MAX_ATTEMPTS = 10;
const CHROMIUM_PREFIX = "chromium%2Fsrc~master~";

class SomTestExpectations extends Polymer.Element {

  static get is() {
    return 'som-test-expectations';
  }

  static get properties() {
    return {
      editedTestName: {
        type: String,
        value: '',
        observer: '_editedTestNameChanged',
      },
      _testExpectationsJson: {
        type: Array,
        value: [],
        observer: '_testExpectationsJsonChanged',
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
      _requestedModifiers: {
        type: Array,
        value: [],
      },
      _reqeustedExpectations: {
        type: Array,
        value: [],
      }
    };
  }

  ready() {
    super.ready();

    this.refresh();
  }

  refresh() {
    let promises = [this.$.testExpectationsAjax.generateRequest().completes];
    Promise.all(promises).then(
        (response) => {
          this._testExpectationsLoaded = true;
        },
        (error) => {
          console.error(error);
        });
  }

  _editedTestNameChanged(testName) {
    if (testName && this._testExpectationsJson) {
      this._openEditor(testName);
    }

    let url = new URL(window.location.href);
    this._requestedModifiers = url.searchParams.getAll('modifiers');
    this._requestedExpectations = url.searchParams.getAll('expectations');
  }

  _testExpectationsJsonChanged(json) {
    if (this.editedTestName && json) {
      this._openEditor(this.editedTestName);
    }
  }

  _onActiveItemChanged(evt) {
    this.$.grid.expandedItems = [evt.detail.value];
  }

  _showTestExpectationsLoading(testExpectationsLoaded, error) {
    return !testExpectationsLoaded && this._haveNoErrors(error);
  }

  _haveNoErrors(error) {
    return !error;
  }

  _shortFileName(fn) {
    if (!fn)
      return '';
    let parts = fn.split('/');
    return parts.pop();
  }

  _onCreateChangeCL(evt) {
    let expectation = this._testExpectationsJson.find((t) => {
      return t.TestName == this.$.editExpectationForm.expectation.TestName;
    }, this) || {};
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
  }

  _pollCLStatus(opt_attempt) {
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
            this._countdown(delay);
            this.$.progress.hidden = false;
            attempt += 1;
            this._pollingTask = Polymer.Async.timeOut.after(delay * 1000).run(
                this._pollCLStatus.bind(this, attempt));
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
  }

  _countdown(delay) {
    if (delay > 0) {
      this._statusMessage =
        `Working... Checking again in ${delay} seconds.`;
      // Cancel existing _countdownTask?
      this._countdownTask = Polymer.Async.timeOut.after(1000).run(
         this._countdown.bind(this, delay - 1));
    }
   }

  _onCancelChangeCL(evt) {
    this.editedTestName = '';
    this.$.editDialog.toggle();
  }

  _onStartEdit(evt) {
      this.editedTestName = evt.target.value;
  }

  _openEditor(testName) {
    if (!this._testExpectationsJson ||
        !this._testExpectationsJson.length > 0) {
      return;
    }
    let expectation = this._testExpectationsJson.find((t) => {
      return t.TestName == testName;
    }) || {};

    if (!expectation.TestName) { // We are creating a new expectation.
      expectation.TestName = testName;
    }

    // Union the existing modifiers with the additional requested modifiers.
    let mods = new Set(expectation.Modifiers);
    for (let m of this._requestedModifiers) {
      mods.add(m);
    }
    expectation.Modifiers = [];
    for (let m of mods.values()) {
      expectation.Modifiers.push(m);
    }

    // Union the existing results with the additional requested results.
    let exps = new Set(expectation.Expectations);
    for (let m of this._requestedExpectations) {
      exps.add(m);
    }
    expectation.Expectations = [];
    for (let e of exps.values()) {
      expectation.Expectations.push(e);
    }

    this.$.editExpectationForm.set('expectation', expectation);
    this.$.editDialog.toggle();
  }

  _cancelPollingTask(evt) {
    if (this._pollingTask) {
      Polymer.Async.timeOut.cancel(this._pollingTask);
    }
    if (this._countdownTask) {
      Polymer.Async.timeOut.cancel(this._countdownTask);
    }
  }
}

customElements.define(SomTestExpectations.is, SomTestExpectations);
