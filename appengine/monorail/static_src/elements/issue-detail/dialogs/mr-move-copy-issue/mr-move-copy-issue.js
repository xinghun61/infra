// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import page from 'page';
import {LitElement, html, css} from 'lit-element';

import {connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import 'elements/framework/mr-autocomplete/mr-autocomplete.js';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';
import {prpcClient} from 'prpc-client-instance.js';

export class MrMoveCopyIssue extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
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
      `,
    ];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <chops-dialog closeOnOutsideClick>
        <div class="target-project-dialog">
          <h3 class="medium-heading">${this._action} issue</h3>
          <div class="input-grid">
            <label for="targetProjectInput">Target project:</label>
            <div>
              <input id="targetProjectInput" />
              <mr-autocomplete
                vocabularyName="project"
                for="targetProjectInput"
              ></mr-autocomplete>
            </div>
          </div>

          ${this._targetProjectError ? html`
            <div class="error">
              ${this._targetProjectError}
            </div>
          ` : ''}

          <div class="edit-actions">
            <chops-button @click=${this.cancel} class="de-emphasized">
              Cancel
            </chops-button>
            <chops-button @click=${this.save} class="emphasized">
              ${this._action} issue
            </chops-button>
          </div>
        </div>
      </chops-dialog>
    `;
  }

  static get properties() {
    return {
      issueRef: {type: Object},
      _action: {type: String},
      _targetProjectError: {type: String},
    };
  }

  stateChanged(state) {
    this.issueRef = issue.issueRef(state);
  }

  open(e) {
    this.shadowRoot.querySelector('chops-dialog').open();
    this._action = e.detail.action;
    this.reset();
  }

  reset() {
    this.shadowRoot.querySelector('#targetProjectInput').value = '';
    this._targetProjectError = '';
  }

  cancel() {
    this.shadowRoot.querySelector('chops-dialog').close();
  }

  save() {
    const method = this._action + 'Issue';
    prpcClient.call('monorail.Issues', method, {
      issueRef: this.issueRef,
      targetProjectName: this.shadowRoot.querySelector(
        '#targetProjectInput').value,
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

customElements.define('mr-move-copy-issue', MrMoveCopyIssue);
