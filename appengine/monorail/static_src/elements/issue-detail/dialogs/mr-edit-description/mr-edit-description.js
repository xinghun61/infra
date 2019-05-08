// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import 'elements/framework/mr-upload/mr-upload.js';
import 'elements/framework/mr-error/mr-error.js';
import {fieldTypes} from 'elements/shared/field-types.js';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import 'elements/chops/chops-checkbox/chops-checkbox.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';


/**
 * `<mr-edit-description>`
 *
 * A dialog to edit descriptions.
 *
 */
export class MrEditDescription extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        chops-dialog {
          --chops-dialog-width: 800px;
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
      `,
    ];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <chops-dialog>
        <h3 class="medium-heading">
          Edit ${this._displayedTitle}
        </h3>
        <textarea
          id="description"
          class="content"
          @keyup=${this._updateDisplayedContent}
          @change=${this._updateDisplayedContent}
          value=${this._displayedContent}
        ></textarea>
        <h3 class="medium-heading">
          Add attachments
        </h3>
        <div class="attachments">
          ${this._attachments && this._attachments.map((attachment) => html`
            <label>
              <chops-checkbox
                type="checkbox"
                checked="true"
                class="kept-attachment"
                data-attachment-id=${attachment.attachmentId}
                @checked-change=${this._keptAttachmentIdsChanged}
              />
              <a href=${attachment.viewUrl} target="_blank">
                ${attachment.filename}
              </a>
            </label>
            <br>
          `)}
          <mr-upload></mr-upload>
        </div>
        <mr-error
          ?hidden=${!this._attachmentError}
        >${this._attachmentError}</mr-error>
        <div class="edit-controls">
          <chops-checkbox
            id="sendEmail"
            ?checked=${this._sendEmail}
            @checked-change=${this._setSendEmail}
          >Send email</chops-checkbox>
          <div>
            <chops-button id="discard" @click=${this.cancel} class="de-emphasized">
              Discard
            </chops-button>
            <chops-button id="save" @click=${this.save} class="emphasized">
              Save changes
            </chops-button>
          </div>
        </div>
      </chops-dialog>
    `;
  }

  static get properties() {
    return {
      comments: {type: Array},
      issueRef: {type: Object},
      _attachmentError: {type: String},
      _attachments: {type: Array},
      _boldLines: {type: Array},
      _displayedContent: {type: String},
      _displayedTitle: {type: String},
      _fieldName: {type: String},
      _keptAttachmentIds: {type: Object},
      _sendEmail: {type: Boolean},
    };
  }

  stateChanged(state) {
    this.comments = issue.comments(state);
    this.issueRef = issue.issueRef(state);
  }

  async open(e) {
    await this.updateComplete;
    this.shadowRoot.querySelector('chops-dialog').open();
    this._fieldName = e.detail.fieldName;
    this.reset();
  }

  async reset() {
    await this.updateComplete;
    this._attachmentError = '';
    this._attachments = [];
    this._boldLines = [];
    this._keptAttachmentIds = new Set();

    const uploader = this.shadowRoot.querySelector('mr-upload');
    if (uploader) {
      uploader.reset();
    }

    // Sets _displayedContent and _displayedTitle.
    this._initializeView(this.comments, this._fieldName);

    this.shadowRoot.querySelectorAll('.kept-attachment').forEach((checkbox) => {
      checkbox.checked = true;
    });
    this.shadowRoot.querySelector('#sendEmail').checked = true;

    this._sendEmail = true;

    // Force description to be set to the property value.
    this.shadowRoot.querySelector('#description').value =
      this._displayedContent;
  }

  async cancel() {
    await this.updateComplete;
    this.shadowRoot.querySelector('chops-dialog').close();
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
      this.shadowRoot.querySelector('chops-dialog').close();
    } catch (e) {
      this._attachmentError = `Error while loading file for attachment: ${
        e.message}`;
    }
  }

  _updateDisplayedContent(e) {
    const target = e.target;
    this._displayedContent = target.value;
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

  _initializeView(comments, fieldName) {
    this._displayedTitle = fieldName ? `${fieldName} Survey` : 'Description';

    if (!comments || comments.length === 0) return;

    // Get description or survey from list of comments.
    for (let i = comments.length - 1; i >= 0; i--) {
      const comment = comments[i];
      if (this._isDescription(comment, fieldName)) {
        if (comment.attachments) {
          this._keptAttachmentIds = new Set(comment.attachments.map(
            (attachment) => Number.parseInt(attachment.attachmentId)));
          this._attachments = comment.attachments;
        }
        this._processRawContent(comment.content);

        break;
      }
    }
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
}

customElements.define('mr-edit-description', MrEditDescription);
