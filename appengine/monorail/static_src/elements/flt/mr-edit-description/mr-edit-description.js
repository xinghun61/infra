// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {fieldTypes} from '../../shared/field-types.js';
import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';
import '../../chops/chops-checkbox/chops-checkbox.js';
import '../../chops/chops-dialog/chops-dialog.js';
import '../shared/mr-flt-styles.js';


/**
 * `<mr-edit-description>`
 *
 * A dialog to edit descriptions.
 *
 */
export class MrEditDescription extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-flt-styles">
        chops-dialog {
          font-size: 85%;
          --chops-dialog-theme: {
            width: 800px;
            max-width: 100%;
          };
        }
        .content {
          padding: 0.5em 0;
          width: 100%;
          box-sizing: border-box;
        }
        .edit-controls {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        textarea.content {
          min-height: 200px;
          max-height: 500px;
          border: var(--chops-accessible-border);
          padding: 0.5em 4px;
          margin: 0.5em 0;
        }
      </style>
      <chops-dialog id='dialog'>
        <h3 class="medium-heading">
          Edit [[_displayedTitle]]
        </h3>
        <textarea
          id="description"
          class="content"
          value="{{_displayedContent::input}}"
        ></textarea>
        <div class="edit-controls">
          <chops-checkbox
            id="sendEmail"
            checked="[[_sendEmail]]"
            on-checked-change="_setSendEmail"
          >Send email</chops-checkbox>
          <div>
            <chops-button id="discard" on-click="cancel" class="de-emphasized">
              Discard changes
            </chops-button>
            <chops-button id="save" on-click="save" class="emphasized">
              Save changes
            </chops-button>
          </div>
        </div>
      </chops-dialog>
    `;
  }

  static get is() {
    return 'mr-edit-description';
  }

  static get properties() {
    return {
      comments: Array,
      issueId: String,
      projectName: String,
      _fieldName: String,
      _sendEmail: Boolean,
      _boldLines: Array,
      _displayedContent: String,
      _displayedTitle: String,
    };
  }

  static get observers() {
    return [
      '_computeDisplayed(comments, _fieldName)',
    ];
  }

  static mapStateToProps(state, element) {
    return {
      comments: state.comments,
      issueId: state.issueId,
      projectName: state.projectName,
    };
  }

  open(e) {
    this.$.dialog.open();
    this._fieldName = e.detail.fieldName;
  }

  _computeDisplayed(comments, fieldName) {
    this._displayedTitle = fieldName ? `${fieldName} Survey` : 'Description';

    if (!comments || comments.length === 0) return;
    let content = '';
    for (const comment of comments.slice().reverse()) {
      if (this._isDescription(comment, fieldName)) {
        content = comment.content;
        break;
      }
    }
    this._processRawContent(content);
  }

  _isDescription(comment, fieldName) {
    if (!comment.descriptionNum) return false;
    if (!fieldName && !comment.approvalRef) return true;
    if (fieldName && comment.approvalRef) {
      return comment.approvalRef.fieldName === fieldName;
    }
  }

  _processRawContent(content) {
    const chunks = content.trim().split(/(<b>[^<\n]+<\/b>)/m);
    const boldLines = [];
    let cleanContent = '';
    chunks.forEach((chunk) => {
      if (chunk.startsWith('<b>') && chunk.endsWith('</b>')) {
        const cleanChunk = chunk.slice(3, -4).trim();
        cleanContent += cleanChunk;
        // Don't add whitespace to boldLines.
        if (/\S/.test(cleanChunk)) {
          boldLines.push(cleanChunk);
        }
      } else {
        cleanContent += chunk;
      }
    });

    this.set('_boldLines', boldLines);
    this._displayedContent = cleanContent;
  }

  _markupNewContent() {
    const lines = this._displayedContent.trim().split('\n');
    const markedLines = lines.map((line) => {
      let markedLine = line;
      const matchingBoldLine = this._boldLines.find(
        (boldLine) => (line.startsWith(boldLine)));
      if (matchingBoldLine) {
        markedLine =
          `<b>${matchingBoldLine}</b>${line.slice(matchingBoldLine.length)}`;
      }
      return markedLine;
    });
    return markedLines.join('\n');
  }

  _setSendEmail(e) {
    this._sendEmail = e.detail.checked;
  }

  cancel() {
    this.$.dialog.close();
  }

  save() {
    const commentContent = this._markupNewContent();
    const sendEmail = this._sendEmail;
    const message = {
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
      isDescription: true,
      commentContent,
      sendEmail,
    };
    if (!this._fieldName) {
      actionCreator.updateIssue(this.dispatchAction.bind(this), message);
    } else {
      message.fieldRef = {
        type: fieldTypes.APPROVAL_TYPE,
        fieldName: this._fieldName,
      };
      actionCreator.updateApproval(this.dispatchAction.bind(this), message);
    }
    this.$.dialog.close();
  }
}

customElements.define(MrEditDescription.is, MrEditDescription);
