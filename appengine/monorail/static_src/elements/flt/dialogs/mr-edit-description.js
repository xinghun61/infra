// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../framework/mr-upload/mr-upload.js';
import '../../mr-error/mr-error.js';
import {fieldTypes} from '../../shared/field-types.js';
import {store, connectStore} from '../../redux/base.js';
import * as issue from '../../redux/issue.js';
import '../../chops/chops-checkbox/chops-checkbox.js';
import '../../chops/chops-dialog/chops-dialog.js';
import '../../shared/mr-shared-styles.js';


/**
 * `<mr-edit-description>`
 *
 * A dialog to edit descriptions.
 *
 */
export class MrEditDescription extends connectStore(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <style include="mr-shared-styles">
        chops-dialog {
          --chops-dialog-theme: {
            width: 800px;
            max-width: 100%;
          };
        }
        textarea {
          font-family: var(--mr-toggled-font-family);
          min-height: 300px;
          max-height: 500px;
          border: var(--chops-accessible-border);
          padding: 0.5em 4px;
          margin: 0.5em 0;
        }
        .attachments {
          margin: 0.5em 0;
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
        <h3 class="medium-heading">
          Add attachments
        </h3>
        <div class="attachments">
          <template is="dom-repeat" items="[[_attachments]]" as="attachment">
            <label title$="[[option.docstring]]">
              <chops-checkbox
                type="checkbox"
                checked="true"
                class="kept-attachment"
                on-checked-change="_keptAttachmentIdsChanged"
                data-attachment-id\$="[[attachment.attachmentId]]"
              />
              <a href="[[attachment.viewUrl]]" target="_blank">
                [[attachment.filename]]
              </a>
            </label>
            <br>
          </template>
          <mr-upload></mr-upload>
        </div>
        <mr-error
          hidden$="[[!_attachmentError]]"
        >[[_attachmentError]]</mr-error>
        <div class="edit-controls">
          <chops-checkbox
            id="sendEmail"
            checked="[[_sendEmail]]"
            on-checked-change="_setSendEmail"
          >Send email</chops-checkbox>
          <div>
            <chops-button id="discard" on-click="cancel" class="de-emphasized">
              Discard
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
      issueRef: Object,
      _attachmentError: String,
      _attachments: Array,
      _boldLines: Array,
      _displayedContent: String,
      _displayedTitle: String,
      _fieldName: String,
      _keptAttachmentIds: Object,
      _sendEmail: Boolean,
    };
  }

  stateChanged(state) {
    this.setProperties({
      comments: issue.comments(state),
      issueRef: issue.issueRef(state),
    });
  }

  _keptAttachmentIdsChanged(e) {
    e.target.checked = e.detail.checked;
    const attachmentId = Number.parseInt(e.target.dataset.attachmentId);
    if (e.target.checked) {
      this._keptAttachmentIds.add(attachmentId);
    } else {
      this._keptAttachmentIds.delete(attachmentId);
    }
  }

  _computeDisplayed(comments, fieldName) {
    this._displayedTitle = fieldName ? `${fieldName} Survey` : 'Description';

    if (!comments || comments.length === 0) return;
    let content = '';
    for (const comment of comments.slice().reverse()) {
      if (this._isDescription(comment, fieldName)) {
        content = comment.content;
        if (comment.attachments) {
          this._keptAttachmentIds = new Set(comment.attachments.map(
            (attachment) => Number.parseInt(attachment.attachmentId)));
          this._attachments = comment.attachments;
        }
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

    this._boldLines = boldLines;
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

  open(e) {
    this.$.dialog.open();
    this._fieldName = e.detail.fieldName;
    this.reset();
  }

  reset() {
    this._attachmentError = '';
    this._attachments = [];
    this._boldLines = [];
    this._displayedContent = '';
    this._keptAttachmentIds = new Set();

    const uploader = this.shadowRoot.querySelector('mr-upload');
    if (uploader) {
      uploader.reset();
    }

    this._computeDisplayed(this.comments, this._fieldName);
    this.shadowRoot.querySelectorAll('.kept-attachment').forEach((checkbox) => {
      checkbox.checked = true;
    });
    this.shadowRoot.querySelector('#sendEmail').checked = true;
  }

  cancel() {
    this.shadowRoot.querySelector('#dialog').close();
  }

  async save() {
    const commentContent = this._markupNewContent();
    const sendEmail = this._sendEmail;
    const keptAttachments = Array.from(this._keptAttachmentIds);
    const message = {
      issueRef: this.issueRef,
      isDescription: true,
      commentContent,
      keptAttachments,
      sendEmail,
    };

    try {
      const uploader = this.shadowRoot.querySelector('mr-upload');
      const uploads = await uploader.loadFiles();
      if (uploads && uploads.length) {
        message.uploads = uploads;
      }

      if (!this._fieldName) {
        store.dispatch(issue.update(message));
      } else {
        // This is editing an approval if there is no field name.
        message.fieldRef = {
          type: fieldTypes.APPROVAL_TYPE,
          fieldName: this._fieldName,
        };
        store.dispatch(issue.updateApproval(message));
      }
      this.$.dialog.close();
    } catch (e) {
      this._attachmentError = `Error while loading file for attachment: ${
        e.message}`;
    }
  }
}

customElements.define(MrEditDescription.is, MrEditDescription);
