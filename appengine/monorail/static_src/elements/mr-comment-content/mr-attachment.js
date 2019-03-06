// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../chops/chops-button/chops-button.js';
import {ReduxMixin, actionCreator} from '../redux/redux-mixin.js';
import '../flt/shared/mr-flt-styles.js';

/**
 * `<mr-attachment>`
 *
 * Display attachments for Monorail comments.
 *
 */
export class MrAttachment extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-flt-styles">
        .attachment-view {
          margin-left: .7em;
        }
        .attachment-download {
          margin-left: .7em
        }
        .attachment-delete {
          float: right;
        }
        .attachment-delete-button {
          color: var(--chops-button-color);
          background: var(--chops-button-bg);
          border-color: transparent;
        }
        .comment-attachment {
          min-width: 20%;
          width: fit-content;
          background: var(--chops-card-details-bg);
          padding: 4px;
          margin: 8px;
          overflow: auto;
        }
        .comment-attachment-header {
          display: flex;
          flex-wrap: nowrap;
        }
        .filename {
          margin-left: .7em;
        }
        .filesize {
          margin-left: .7em;
        }
        .preview {
          border: 2px solid #c3d9ff;
          padding: 1px;
          max-width: 98%;
        }
        .preview:hover {
          border: 2px solid blue;
        }
      </style>
      <div class="comment-attachment">
        <template is="dom-if" if="[[canDelete]]">
          <div class="attachment-delete">
            <chops-button
              class="attachment-delete-button"
              on-click="_deleteAttachment"
            >
              <template is="dom-if" if="[[attachment.isDeleted]]">
                Undelete
              </template>
              <template is="dom-if" if="[[!attachment.isDeleted]]">
                Delete
              </template>
            </chops-button>
          </div>
        </template>
        <div class="filename">
          <template is="dom-if" if="[[attachment.isDeleted]]">
            [Deleted]
          </template>
          <b>[[attachment.filename]]</b>
        </div>
        <template is="dom-if" if="[[!attachment.isDeleted]]">
          <div class="comment-attachment-header">
            <div class="filesize">[[_bytesOrKbOrMb(attachment.size)]]</div>
            <template is="dom-if" if="[[!attachment.isDeleted]]">
              <div class="attachment-view">
                <a href="[[attachment.viewUrl]]" target="_blank">View</a>
              </div>
              <div class="attachment-download">
                <a href="[[attachment.downloadUrl]]" target="_blank">Download</a>
              </div>
            </template>
          </div>
          <template is="dom-if" if="[[attachment.thumbnailUrl]]">
            <a href="[[attachment.viewUrl]]" target="_blank">
              <img
                class="preview"
                src\$="[[attachment.thumbnailUrl]]"
              >
            </a>
          </template>
          <template is="dom-if" if="[[_isVideo(attachment.contentType)]]">
            <video
              src\$="[[attachment.viewUrl]]"
              class="preview"
              controls
              width="640"
              preload="metadata"
            ></video>
          </template>
        </template>
      </div>
    `;
  }

  static get is() {
    return 'mr-attachment';
  }

  static get properties() {
    return {
      attachment: Object,
      projectName: String,
      localId: Number,
      sequenceNum: Number,
      canDelete: Boolean,
    };
  }

  _isVideo(contentType) {
    if (!contentType) return;
    return contentType.startsWith('video/');
  }

  _bytesOrKbOrMb(numBytes) {
    if (numBytes < 1024) {
      return `${numBytes} bytes`;  // e.g., 128 bytes
    } else if (numBytes < 99 * 1024) {
      return `${(numBytes / 1024).toFixed(1)} KB`;  // e.g. 23.4 KB
    } else if (numBytes < 1024 * 1024) {
      return `${(numBytes / 1024).toFixed(0)} KB`;  // e.g., 219 KB
    } else if (numBytes < 99 * 1024 * 1024) {
      return `${(numBytes / 1024 / 1024).toFixed(1)} MB`;  // e.g., 21.9 MB
    } else {
      return `${(numBytes / 1024 / 1024).toFixed(0)} MB`;  // e.g., 100 MB
    }
  }

  _deleteAttachment() {
    const issueRef = {
      projectName: this.projectName,
      localId: this.localId,
    };

    const promise = window.prpcClient.call(
      'monorail.Issues', 'DeleteAttachment',
      {
        issueRef,
        sequenceNum: this.sequenceNum,
        attachmentId: this.attachment.attachmentId,
        delete: !this.attachment.isDeleted,
      });

    promise.then(() => {
      actionCreator.fetchComments(this.dispatchAction.bind(this), {issueRef});
    }, (error) => {
      console.log('Failed to (un)delete attachment', error);
    });
  }
}
customElements.define(MrAttachment.is, MrAttachment);
