'use strict';

class TsTreeView extends Polymer.Element {

  static get is() {
    return 'ts-tree-view';
  }

  static get properties() {
    return {
      statusLimit: Number,
      _statusLimit: {
        type: Number,
        value: 25,
        computed: '_computeStatusLimit(statusLimit)',
      },
      tree: {
        type: Object,
        observer: 'refresh',
      },
      _hasError: {
        type: Boolean,
        computed: '_computeHasError(_hasStatusApp, _statusError)',
        value: false,
      },
      _latestStatus: {
        type: Object,
        computed: '_computeLatestStatus(_statusList)',
      },
      _statusError: Object,
      _statusList: Array,
    };
  }

  refresh() {
    if (!this.tree.status_url) {
      return;
    }
    this.$.treeStatusAjax.generateRequest();
  }

  _computeHasError(hasStatusApp, error) {
    return hasStatusApp && !!error && Object.keys(error).length > 0;
  }

  _computeLatestStatus(statusList) {
    if (!statusList || !statusList.length) return;
    return statusList[0];
  }

  _computeStatusLimit(statusLimit) {
    return statusLimit || 25;
  }

  // Processing JSON data for display.
  _computeEmail(status) {
    if (!status || !status.username) {
      return '';
    }
    return status.username;
  }

  _computeStatus(status) {
    if (!status) {
      return '';
    }
    return status.general_state;
  }

  _computeMessage(status) {
    if (!status || !status.message) {
      return 'Unknown';
    }
    return status.message;
  }

  _computeTime(status) {
    if (!status || !status.date) {
      return 'Unknown';
    }
    let time = moment.tz(status.date, 'Atlantic/Reykjavik');
    return time.tz('America/Los_Angeles').format('ddd, DD MMM hh:mm');
  }

  _computeUsername(status) {
    if (!status || !status.username) return;
    let email = status.username;
    let cutoff = email.indexOf('@');
    if (cutoff < 0) {
      return 'Unknown';
    }
    return email.substring(0, cutoff);
  }
}

customElements.define(TsTreeView.is, TsTreeView);
