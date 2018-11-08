'use strict';

const MAX_ATTEMPTS = 10;
const CHROMIUM_PREFIX = "chromium%2Fsrc~master~";

const gerritHost = 'https://chromium-review.googlesource.com';

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
      signedIn: {
        type: Boolean,
        value: false
      },
      clientId: {
        type: String,
        computed: '_computeClientId()'
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

  _computeClientId() {
    if (window.location.host == 'sheriff-o-matic.appspot.com') {
      return '297387252952-io4k56a9uagle7rq4o8b7sclfih6136c.apps.googleusercontent.com';
    }

    // Staging is whitelisted for localhost/dev.
    return '408214842030-n7qkqet08nqmsvoap6qkik6euga4v41v.apps.googleusercontent.com';
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
    if (!this.$.signIn.signedIn) {
      ga('send', 'event', this.nodeName.toLocaleLowerCase(),
          'create-change-cl-start', 'logged-out');
      this.$.signIn.signIn();
      return;
    }
    ga('send', 'event', this.nodeName.toLocaleLowerCase(),
        'create-change-cl-start', 'logged-in');
    this._createCLStartTime = new Date();
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

    try {
      fetch('/api/v1/testexpectation', {
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify(formData),
      }).then(resp => {
        if (resp.ok) {
          resp.json().then(body => {
            this.$.editDialog.toggle();
            this.$.changeListStatusDialog.toggle();
            this._errorMessage = '';
            this._statusMessage = '';
            this._createCL(body, formData);
          }).catch(err => {
            this._reportError('error decoding response JSON: ' + err);
          });
        } else {
          console.error('bad response', resp);
          this._reportError('bad response: ' + resp.status);
        }
      }).catch(err => {
        this._reportError('error creating changes for CL: ' + err)
      });

    } catch (error) {
      this._reportError('Failed to update layout expectation: ' + error);
      this.$.editDialog.toggle();
    }
  }

  // TODO(seanmccullough): Simplify this mess of Promises.
  _createCL(changes, changeInfo) {
    let changeInput = {
      // https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#change-input
      project: 'chromium/src',
      branch: 'master',
      subject: 'update ' + changeInfo.TestName + ' expectations',
      status: 'DRAFT',
      topic: ''
    };

    let authPostJson =
        '?$m=POST&$ct=application/json%3B%20charset%3DUTF-8&access_token=' +
         this._oAuthToken.access_token;

    let authPutText = '?$m=PUT&$ct=text/plain&access_token=' +
        this._oAuthToken.access_token;

    this._statusMessage = 'Creating CL...';
    let createChange = fetch(gerritHost + '/changes/' + authPostJson, {
      method: 'POST',
      body: JSON.stringify(changeInput),
      mode: 'cors',
      headers: new Headers({
          'Content-Type': 'text/plain; charset=UTF-8'
      })
    }).then(resp => {
      if (!resp.ok) {
        console.error('createChange resp not ok', resp);
        this._reportError('Could not create change: ' + resp.status);
        return;
      }
      return resp.text();
    }).catch(err => {
       console.error('createChange resp not ok', err);
       this._reportError('Could not create change: ' + err);
    });

    let editFiles = createChange.then(changeInfoStr => {
      // Strip jsonp prefix.
      this._changeInfo = JSON.parse(changeInfoStr.substr(4));
      let changeRequests = [];
      this._statusMessage = 'Editing file(s)...';
      for (let fileName in changes.CL) {
        let contents = changes.CL[fileName];
        let path = '/changes/' + this._changeInfo.change_id + '/edit/' +
            encodeURIComponent(fileName) + authPutText;
        changeRequests.push(fetch(gerritHost + path, {
           method: 'POST',
           body: contents,
           mode: 'cors',
           headers: new Headers({
               'Content-Type': 'text/plain; charset=UTF-8'
           })
       }));
      }

      return Promise.all(changeRequests);
    }).catch(err => {
      console.error('createChange resp not ok', err);
      this._reportError('Could not create change: ' + err);
    });

    let publish = editFiles.then(resps => {
      for (let r in resps) {
        if (!resps[r].ok) {
          console.error('resp not ok', resps[r]);
          this._reportError('Could not edit file: ' + resps[r].status);
          return;
        }
      }

      this._statusMessage = 'Publishing...';
      let path = '/changes/' + this._changeInfo.change_id + '/edit:publish';
      return fetch(gerritHost + path + authPostJson, {
         method: 'POST',
         body: JSON.stringify({notify: "NONE"}),
         mode: 'cors',
         headers: new Headers({
             'Content-Type': 'text/plain; charset=UTF-8'
         })
      });
    }).catch(err => {
      console.error('could not edit files', err);
      this._reportError('Could not create change: ' + err);
    });

    publish.then(resp => {
       if (!resp.ok) {
         console.error('resp not ok', resp);
         this._reportError('Error publishing change: ' + resp.status);
         return;
       }
       return resp.text();
    }).then(respStr => {
       // Success. Update the status dialog with a link to the CL.
       this.$.changeListStatusDialog.toggle();
       this._changeListId = this._changeInfo.change_id;
       if (this._changeListId.startsWith(CHROMIUM_PREFIX)) {
         this._changeListId =
             this._changeListId.substr(CHROMIUM_PREFIX.length);
       }
       this.$.changeListDialog.toggle();
       let elapsed = new Date().getTime() - this._createCLStartTime.getTime();
       ga('send', 'event', this.nodeName.toLocaleLowerCase(),
           'create-change-cl-end', 'success', elapsed);
    }).catch(err => {
      console.error('could not publish change', err);
      this._reportError('Could not publish change: ' + err);
    });
  }

  _reportError(msg) {
    console.error(msg);
    let elapsed = new Date().getTime() - this._createCLStartTime.getTime();
    ga('send', 'event', this.nodeName.toLocaleLowerCase(),
        'create-change-cl-end', 'error', elapsed);
    this._errorMessage = msg;
    this._statusMessage = '';
    this.$.progress.hidden = true;
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
    ga('send', 'event', this.nodeName.toLocaleLowerCase(), 'open-editor');
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

  handleSignin(resp) {
    this._oAuthToken = resp.detail;
  }
}

customElements.define(SomTestExpectations.is, SomTestExpectations);
