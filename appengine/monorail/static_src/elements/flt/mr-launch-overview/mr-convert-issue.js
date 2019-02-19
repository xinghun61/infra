// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../shared/mr-flt-styles.js';

/**
 * `<mr-convert-issue>`
 *
 * This allows a user to update the structure of an issue to that of
 * a chosen project template.
 *
 */
export class MrConvertIssue extends PolymerElement {
  static get template() {
    return html`
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style include="mr-flt-styles">
      :host {
        padding: 1em;
          display: block;
          font-size: 12px;
          --mr-edit-field-styles: {
            box-sizing: border-box;
            width: 95%;
            padding: 0.25em 4px;
          };
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: right;
        }
        .error {
          max-width: 100%;
          color: red;
          margin-bottom: 1em;
        }
        label {
          font-weight: bold;
          text-align: right;
        }
        .input-grid {
          padding: 0.5em 0;
          display: grid;
          max-width: 100%;
          grid-gap: 10px;
          grid-template-columns: 120px auto;
          align-items: flex-start;
        }
    </style>
    <h3 class="medium-heading">Convert issue to new template structure</h3>
    <form id="convertIssueForm">
      <div class="input-grid">
        <label for="templateInput">Pick a template: </label>
        <select id="templateInput" on-change="_templateInputChanged">
          <option value="">--Please choose a project template--</option>
          <template is="dom-repeat" items="[[projectTemplates]]" as="projTempl">
            <option value="[[projTempl.templateName]]">[[  projTempl.templateName  ]]</option>
          </template>
        </select>
        <label for="commentContent">Comment: </label>
        <textarea id="commentContent" placeholder="Add a comment"></textarea>
        <span></span>
        <chops-checkbox on-checked-change="_sendEmailChecked" checked="[[sendEmail]]">Send email</chops-checkbox>
      </div>
      <div class="error" hidden\$=[[!convertIssueError]]>[[convertIssueError.description]]</div>
      <div class="edit-actions">
        <chops-button on-click="discard" class="de-emphasized discard-button">
          <i class="material-icons">close</i>
          Discard changes
        </chops-button>
        <chops-button on-click="save" class="emphasized" disabled\$="[[!selectedTemplate]]">
          <i class="material-icons">create</i>
          Convert issue
        </chops-button>
      </div>
    </form>
    `;
  }

  static get is() {
    return 'mr-convert-issue';
  }

  static get properties() {
    return {
      convertIssueError: Object,
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

  _sendEmailChecked(evt) {
    this.sendEmail = evt.detail.checked;
  }

  _templateInputChanged() {
    this.selectedTemplate = this.shadowRoot.querySelector("#templateInput").value;
  }

  reset() {
    this.$.convertIssueForm.reset()
  }

  save() {
    this.dispatchEvent(new CustomEvent("save"))
  }

  discard(){
    this.reset();
    this.dispatchEvent(new CustomEvent("discard"))
  }

}

customElements.define(MrConvertIssue.is, MrConvertIssue);
