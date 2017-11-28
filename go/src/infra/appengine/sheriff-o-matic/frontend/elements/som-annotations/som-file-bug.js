'use strict';

/**
 * `<som-file-bug>` ....
 *
 *   Element description here.
 *
 * @customElement
 * @polymer
 */
class SomFileBug extends Polymer.mixinBehaviors([AnnotationManagerBehavior, PostBehavior], Polymer.Element) {
  static get is() { return 'som-file-bug'; }

  static get properties() {
    return {
      /** The bug's summary. */
      summary: String,
      /** The user filing the bug. */
      creator: {
        type: String,
        observer: '_creatorChanged',
      },
      /** The bug's description. */
      description: String,
      /** The bug's labels. */
      labels: Array,
      /** The bug's cc list. */
      cc: Array,
      /** The bug's priority. */
      priority: String,
      _fileBugErrorMessage: {
        type: String,
        value: '',
      },
      filedBugId: String,
    }
  }

  open() {
    this.$.fileBugDialog.open();
  }

  close() {
    this.$.fileBugDialog.close();
  }

  _creatorChanged(creator) {
    if (!this.cc || !this.cc.length) {
      this.cc = [creator];
    }
  }

  _fileBug() {
    let error = false;
    if (this.$.summary.value == "") {
      error = true;
      this.$.summary.invalid = true;
    }
    if (this.$.description.value == "") {
      error = true;
      this.$.description.invalid = true;
    }
    if (error) {
      this._fileBugErrorMessage = 'Please fill in summary and description fields.'
      return
    } else {
      let labels = this._stringToArray(this.$.labels.value);
      if(this.$.priority.selectedItemLabel) {
        labels.push(this.$.priority.selectedItemLabel);
      }

      let bugData = {
        Summary: this.$.summary.value,
        Description: this.$.description.value,
        Cc: this._stringToArray(this.$.cc.value),
        Labels: labels,
      }

      return this
          .postJSON('/api/v1/filebug/', bugData)
          .then(jsonParsePromise)
          .catch((error) => {
            this._fileBugErrorMessage = 'Error trying to create new issue: ' + error;
          })
          .then(this._fileBugResponse.bind(this));
    }
  }

  _fileBugResponse(response) {
    if (response.issue && response.issue.id) {
      this.filedBugId = response.issue.id.toString();
    } else {
       this._fileBugErrorMessage = 'Error, no issue or issue id found: ' + response;
    }

    this.fire('success');
  }

  showBugFiledDialog() {
    this._fileBugErrorMessage = '';
    this.$.fileBugDialog.close();
    this.$.bugFiledDialog.open();
  }


  _arrayToString(arr) {
    return arr.join(", ");
  }

  _stringToArray(str) {
    if (str && str != "") {
      return str.split(",").map(item => {
        return item.trim();
      })
    }
    return [];
  }
}

customElements.define(SomFileBug.is, SomFileBug);
