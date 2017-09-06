'use strict';

class SomTreeStatusView extends Polymer.mixinBehaviors(
    [TreeStatusBehavior], Polymer.Element) {

  static get is() {
    return 'som-tree-status-view';
  }

  static get properties() {
    return {
      statusLimit: {
        type: Number,
        value: 25,
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
      _hasStatusApp: {
        type: Boolean,
        computed: 'hasStatusApp(tree.name)',
      },
      _latestStatus: {
        type: Object,
        computed: '_computeLatestStatus(_statusList)',
      },
      _statusError: Object,
      _statusList: Array,
      _statusUrl: {
        type: String,
        computed: 'getStatusApp(tree.name)',
      },
    };
  }

  refresh() {
    if (!this._hasStatusApp) {
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

customElements.define(SomTreeStatusView.is, SomTreeStatusView);
