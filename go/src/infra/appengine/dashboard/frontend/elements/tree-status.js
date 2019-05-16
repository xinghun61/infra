// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {timeOut} from '@polymer/polymer/lib/utils/async.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';

const RELOAD_TIME = 5 * 60 * 1000;

/**
 * `<tree-status>`
 *
 * displays the status found at infra-status
 */
export class TreeStatus extends PolymerElement{
  static get template() {
    return html`
      <style>
        .closed {
          background-color: #E98080;
        }
        .open {
          background-color: #8FDF5F;
        }
        .tree-banner {
          border: 1px solid #ccc;
          box-sizing: border-box;
          color: #222;
          margin: 0.5em auto;
          padding: 0.5em 8px;
          width: 100%;
        }
      </style>
      <div class="tree-banner" hidden$="[[!_hasError]]">
        Error fetching tree status
      </div>
      <div class$="tree-banner [[_status]]" hidden$="[[_hasError]]">
        [[_statusInfo]]: <a href="https://infra-status.appspot.com">[[_message]]</a>
      </div>
    `;
  }
  static get is() { return 'tree-status'; }

  ready() {
    super.ready();
    this._getTreeStatus();
    this._refresh();
  }

  static get properties() {
    return {
      _message: {
        type: String,
        computed: '_computeMessage(_statusJson)',
      },

      _status: {
        type: String,
        computed: '_computeStatus(_statusJson)',
      },

      _statusInfo: {
        type: String,
        computed: '_computeStatusInfo(_statusJson)',
      },

      _hasError: {
        type: Boolean,
        computed: '_computeHasError(_statusErrorJson)',
        value: false,
      },

      _statusErrorJson: Object,
      _statusJson: Object,
    }
  }
  _computeMessage(json) {
    return json.message ? json.message : 'Unknown';
  }

  _computeStatusInfo(json) {
    if (!json) {
      return 'No json'
    }
    let state = json.general_state ? json.general_state : 'Unknown';
    let username = json.username ? json.username : 'Unknown';
    let date = json.date ? `${json.date.split(".")[0]} GMT` : 'Unknown';
    return `Tree is ${state}. ${date} ${username}`;
  }

  _computeStatus(json) {
    return (json && json.general_state) ? json.general_state : 'Unknown';
  }

  _computeHasError(json) {
    return !!json;
  }

  _refresh() {
    timeOut.run(() => {
      this._getTreeStatus();
    }, RELOAD_TIME);
  }

  _getTreeStatus() {
    window.fetch(
	'https://infra-status.appspot.com/current?format=json'
    ).then((resp) => resp.json()).then((resp) => {
      this._statusJson = resp;
    });
  }
}
customElements.define(TreeStatus.is, TreeStatus);
