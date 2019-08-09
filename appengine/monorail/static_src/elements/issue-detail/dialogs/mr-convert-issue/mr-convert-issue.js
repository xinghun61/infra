// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as project from 'elements/reducers/project.js';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import 'elements/framework/mr-error/mr-error.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';

// TODO(zhangtiff): Make dialog components subclass chops-dialog instead of
// using slots/containment once we switch to LitElement.
/**
 * `<mr-convert-issue>`
 *
 * This allows a user to update the structure of an issue to that of
 * a chosen project template.
 *
 */
export class MrConvertIssue extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        label {
          font-weight: bold;
          text-align: right;
        }
        form {
          padding: 1em 8px;
          display: block;
          font-size: var(--chops-main-font-size);
        }
        textarea {
          font-family: var(--mr-toggled-font-family);
          min-height: 80px;
          border: var(--chops-accessible-border);
          padding: 0.5em 4px;
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: right;
        }
      `,
    ];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <chops-dialog closeOnOutsideClick>
        <h3 class="medium-heading">Convert issue to new template structure</h3>
        <form id="convertIssueForm">
          <div class="input-grid">
            <label for="templateInput">Pick a template: </label>
            <select id="templateInput" @change=${this._templateInputChanged}>
              <option value="">--Please choose a project template--</option>
              ${this.projectTemplates.map((projTempl) => html`
                <option value=${projTempl.templateName}>
                  ${projTempl.templateName}
                </option>`)}
            </select>
            <label for="commentContent">Comment: </label>
            <textarea id="commentContent" placeholder="Add a comment"></textarea>
            <span></span>
            <chops-checkbox
              @checked-change=${this._sendEmailChecked}
              checked=${this.sendEmail}
            >Send email</chops-checkbox>
          </div>
          <mr-error ?hidden=${!this.convertIssueError}>
            ${this.convertIssueError && this.convertIssueError.description}
          </mr-error>
          <div class="edit-actions">
            <chops-button @click=${this.close} class="de-emphasized discard-button">
              Discard
            </chops-button>
            <chops-button @click=${this.save} class="emphasized" ?disabled=${!this.selectedTemplate}>
              Convert issue
            </chops-button>
          </div>
        </form>
      </chops-dialog>
    `;
  }

  static get properties() {
    return {
      convertingIssue: {
        type: Boolean,
      },
      convertIssueError: {
        type: Object,
      },
      issuePermissions: {
        type: Object,
      },
      issueRef: {
        type: Object,
      },
      projectTemplates: {
        type: Array,
      },
      selectedTemplate: {
        type: String,
      },
      sendEmail: {
        type: Boolean,
      },
    };
  }

  stateChanged(state) {
    this.convertingIssue = issue.requests(state).convert.requesting;
    this.convertIssueError = issue.requests(state).convert.error;
    this.issueRef = issue.issueRef(state);
    this.issuePermissions = issue.permissions(state);
    this.projectTemplates = project.project(state).templates;
  }

  constructor() {
    super();
    this.selectedTemplate = '';
    this.sendEmail = true;
  }

  updated(changedProperties) {
    if (changedProperties.has('convertingIssue')) {
      if (!this.convertingIssue && !this.convertIssueError) {
        this.close();
      }
    }
  }

  open() {
    this.reset();
    const dialog = this.shadowRoot.querySelector('chops-dialog');
    dialog.open();
  }

  close() {
    const dialog = this.shadowRoot.querySelector('chops-dialog');
    dialog.close();
  }

  reset() {
    this.shadowRoot.querySelector('#convertIssueForm').reset();
  }

  save() {
    const commentContent = this.shadowRoot.querySelector('#commentContent');
    store.dispatch(issue.convert({
      issueRef: this.issueRef,
      templateName: this.selectedTemplate,
      commentContent: commentContent.value,
      sendEmail: this.sendEmail,
    }));
  }

  _sendEmailChecked(evt) {
    this.sendEmail = evt.detail.checked;
  }

  _templateInputChanged() {
    this.selectedTemplate = this.shadowRoot.querySelector(
        '#templateInput').value;
  }
}

customElements.define('mr-convert-issue', MrConvertIssue);
