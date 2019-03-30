// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import page from 'page';
import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';
import '../../chops/chops-button/chops-button.js';
import '../../chops/chops-dialog/chops-dialog.js';
import '../../shared/mr-shared-styles.js';

export class MrMoveCopyIssue extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style include="mr-shared-styles">
        .target-project-dialog {
          display: block;
          font-size: var(--chops-main-font-size);
        }
        .error {
          max-width: 100%;
          color: red;
          margin-bottom: 1em;
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: right;
        }
        input {
          box-sizing: border-box;
          width: 95%;
          padding: 0.25em 4px;
        }
      </style>
      <chops-dialog id="dialog">
        <div class="target-project-dialog">
          <h3 class="medium-heading">[[_action]] issue</h3>
          <div class="input-grid">
            <label for="targetProjectInput">Target project:</label>
            <input id="targetProjectInput"></input>
          </div>

          <div class="error">
            <template is="dom-if" if="[[_targetProjectError]]">
              [[_targetProjectError]]
            </template>
          </div>

          <div class="edit-actions">
            <chops-button on-click="cancel" class="de-emphasized">
              Cancel
            </chops-button>
            <chops-button on-click="save" class="emphasized">
              [[_action]] issue
            </chops-button>
          </div>
        </div>
      </chops-dialog>
    `;
  }

  static get is() {
    return 'mr-move-copy-issue';
  }

  static get properties() {
    return {
      issueRef: Object,
      _action: String,
      _targetProjectError: String,
    };
  }

  static mapStateToProps(state, element) {
    return {
      issueRef: issue.issueRef(state),
    };
  }

  open(e) {
    this.$.dialog.open();
    this._action = e.detail.action;
    this.reset();
  }

  reset() {
    this.$.targetProjectInput.value = '';
    this._targetProjectError = '';
  }

  cancel() {
    this.$.dialog.close();
  }

  save() {
    const method = this._action + 'Issue';
    window.prpcClient.call('monorail.Issues', method, {
      issueRef: this.issueRef,
      targetProjectName: this.$.targetProjectInput.value,
    }).then((response) => {
      const projectName = response.newIssueRef.projectName;
      const localId = response.newIssueRef.localId;
      page(`/p/${projectName}/issues/detail?id=${localId}`);
      this.cancel();
    }, (error) => {
      this._targetProjectError = error;
    });
  }
}

customElements.define(MrMoveCopyIssue.is, MrMoveCopyIssue);
