'use strict';

/**
 * `<som-file-bug>`
 *
 * A form used to file a bug in monorail.
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
      /** The bug's description. */
      description: String,
      /** The bug's labels. */
      labels: Array,
      /** The bug's cc list. */
      cc: Array,
      /** The bug's priority. */
      priority: String,
      /** The id of the new bug. */
      bugId: Number,
      _statusMessage: {
        type: String,
        value: '',
      }
    }
  }

  _handleFileBug(evt) {

    let bugData = {
      Summary: this.$.summary.value,
      Description: this.$.description.value,
      Cc: this._stringToArray(this.$.cc.value),
      Labels: this._stringToArray(
          this.$.labels.value + ',' + this.$.priority.selectedItemLabel),
    }

    return this
        .postJSON('/api/v1/filebug/', bugData)
        .then(jsonParsePromise)
        .catch((error) => {
          this._statusMessage = 'Error trying to create new issue: ' + error;
        }
        .then(this._postResponse.bind(this));
  }

  _postResponse(response) {
    if (response.issue && response.issue.id) {
      this.bugId = response.issue.id;
    };
    return response;
  }

  _arrayToString(arr) {
    return arr.join(", ");
  }

  _stringToArray(str) {
    return str.split(",").map(item => {
      return item.trim();
    })
  }

}
customElements.define(SomFileBug.is, SomFileBug);
