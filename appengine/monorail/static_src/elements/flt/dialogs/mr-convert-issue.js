// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';
import * as project from '../../redux/project.js';
import '../../chops/chops-button/chops-button.js';
import '../../chops/chops-dialog/chops-dialog.js';
import '../../mr-error/mr-error.js';
import '../../shared/mr-shared-styles.js';

// TODO(zhangtiff): Make dialog components subclass chops-dialog instead of
// using slots/containment once we switch to LitElement.
/**
 * `<mr-convert-issue>`
 *
 * This allows a user to update the structure of an issue to that of
 * a chosen project template.
 *
 */
export class MrConvertIssue extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-shared-styles">
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
          min-height: 80px;
          border: var(--chops-accessible-border);
          padding: 0.5em 4px;
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: right;
        }
      </style>
      <chops-dialog>
        <h3 class="medium-heading">Convert issue to new template structure</h3>
        <form id="convertIssueForm">
          <div class="input-grid">
            <label for="templateInput">Pick a template: </label>
            <select id="templateInput" on-change="_templateInputChanged">
              <option value="">--Please choose a project template--</option>
              <template is="dom-repeat" items="[[projectTemplates]]" as="projTempl">
                <option value="[[projTempl.templateName]]">
                  [[projTempl.templateName]]
                </option>
              </template>
            </select>
            <label for="commentContent">Comment: </label>
            <textarea id="commentContent" placeholder="Add a comment"></textarea>
            <span></span>
            <chops-checkbox
              on-checked-change="_sendEmailChecked"
              checked="[[sendEmail]]"
            >Send email</chops-checkbox>
          </div>
          <mr-error hidden\$=[[!convertIssueError]]>
            [[convertIssueError.description]]
          </mr-error>
          <div class="edit-actions">
            <chops-button on-click="close" class="de-emphasized discard-button">
              Discard
            </chops-button>
            <chops-button on-click="save" class="emphasized" disabled\$="[[!selectedTemplate]]">
              Convert issue
            </chops-button>
          </div>
        </form>
      </chops-dialog>
    `;
  }

  static get is() {
    return 'mr-convert-issue';
  }

  static get properties() {
    return {
      convertingIssue: {
        type: Boolean,
        observer: '_convertingIssueChanged',
      },
      convertIssueError: Object,
      issuePermissions: Object,
      issueRef: Object,
      projectTemplates: Array,
      selectedTemplate: {
        type: String,
        // value needs to be set for save button to be disabled the first time.
        value: '',
      },
      sendEmail: {
        type: Boolean,
        value: true,
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      convertingIssue: state.requests.convertIssue.requesting,
      convertIssueError: state.requests.convertIssue.error,
      issueRef: issue.issueRef(state),
      issuePermissions: state.issuePermissions,
      projectTemplates: project.project(state).templates,
    };
  }

  open() {
    this.reset();
    this.shadowRoot.querySelector('chops-dialog').open();
  }

  close() {
    this.shadowRoot.querySelector('chops-dialog').close();
  }

  reset() {
    this.shadowRoot.querySelector('#convertIssueForm').reset();
  }

  save() {
    const commentContent = this.shadowRoot.querySelector('#commentContent');
    this.dispatchAction(issue.convert({
      issueRef: this.issueRef,
      templateName: this.selectedTemplate,
      commentContent: commentContent.value,
      sendEmail: this.sendEmail,
    }));
  }

  _convertingIssueChanged(isConversionInFlight) {
    if (!isConversionInFlight && !this.convertIssueError) {
      this.close();
    }
  }

  _sendEmailChecked(evt) {
    this.sendEmail = evt.detail.checked;
  }

  _templateInputChanged() {
    this.selectedTemplate = this.shadowRoot.querySelector(
      '#templateInput').value;
  }
}

customElements.define(MrConvertIssue.is, MrConvertIssue);
