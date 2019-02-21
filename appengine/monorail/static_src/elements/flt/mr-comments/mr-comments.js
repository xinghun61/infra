// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-button/chops-button.js';
import '../../chops/chops-timestamp/chops-timestamp.js';
import '../../mr-comment-content/mr-comment-content.js';
import '../../mr-dropdown/mr-dropdown.js';
import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';
import '../shared/mr-flt-styles.js';

// Match: projectName:localIdFormat
const ISSUE_ID_REGEX = /(?:-?([a-z0-9-]+):)?(\d+)/i;
const ISSUE_REF_FIELD_NAMES = [
  'Blocking',
  'Blockedon',
  'Mergedinto',
];
const ISSUE_EDIT_PERMISSION = 'editissue';

/**
 * `<mr-comments>`
 *
 * Display Monorail comments in a dense and compact way. Currently used by the
 * feature launch tracking page.
 *
 */
export class MrComments extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-flt-styles">
        button.toggle {
          background: none;
          color: var(--chops-link-color);
          border: 0;
          border-bottom: var(--chops-normal-border);
          width: 100%;
          padding: 0.5em 0;
          text-align: left;
        }
        button.toggle:hover {
          cursor: pointer;
          text-decoration: underline;
        }
        button.toggle[hidden], .card-comment[hidden] {
          display: none;
        }
        textarea {
          width: 100%;
          margin: 0.5em 0;
          box-sizing: border-box;
          border: var(--chops-accessible-border);
          height: 5em;
          transition: height 0.1s ease-in-out;
          padding: 0.5em 4px;
        }
        .card-comment {
          border-bottom: var(--chops-normal-border);
          padding: 1em 0;
        }
        .comment-header {
          color: hsl(0, 0%, 39%);
          margin-bottom: 0.5em;
          width: 100%;
          display: block;
        }
        .comment-options {
          float: right;
          font-size: 0.9em;
          text-align: right;
          text-decoration: none;
        }
        .comment-attachment {
          min-width: 20%;
          min-hegiht: 28px;
          width: fit-content;
          background: var(--chops-card-details-bg);
          padding: 4px;
          margin: 8px;
        }
        .comment-attachment-header {
          display: flex;
          flex-wrap: nowrap;
        }
        .filesize {
          margin-left: .7em;
        }
        .filename {
          margin-left: .7em;
        }
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
        .preview {
          border: 2px solid #c3d9ff;
          padding: 1px;
          max-width: 98%;
        }
        .preview:hover {
          border: 2px solid blue;
        }
        .deleted-comment-notice {
          color: #888;
        }
        .issue-diff {
          display: inline-block;
          font-size: 80%;
          border-radius: 5px;
          padding: 0.5em 8px;
          width: auto;
          background: hsl(227, 100%, 98%);
          border: var(--chops-normal-border);
          margin-bottom: 0.5em;
        }
      </style>
      <button on-click="toggleComments" class="toggle" hidden\$="[[_hideToggle]]">
        [[_computeCommentToggleVerb(_commentsHidden)]] [[_commentsHiddenCount]] older [[_pluralize(_commentsHiddenCount, 'comment')]].
      </button>
      <template is="dom-repeat" items="[[comments]]" as="comment">
        <div class="card-comment" hidden\$="[[_computeCommentHidden(_commentsHidden,_commentsHiddenCount,index)]]">
          <span role="heading" aria-level\$="[[headingLevel]]" class="comment-header">
            Comment [[comment.sequenceNum]] by
            <mr-user-link display-name="[[comment.commenter.displayName]]" user-id="[[comment.commenter.userId]]"></mr-user-link> on
            <chops-timestamp timestamp="[[comment.timestamp]]"></chops-timestamp>
            <template is="dom-if" if="[[_offerCommentOptions(comment)]]">
              <div class="comment-options">
                <mr-dropdown
                  items="[[_getCommentOptions(_expandedDeletedComments, comment)]]"
                  icon="more_vert"
                ></mr-dropdown>
              </div>
            </template>
          </span>
          <template is="dom-if" if="[[_hideDeletedComment(_expandedDeletedComments, comment)]]">
            <span class="deleted-comment-notice">
              Deleted comment
            </span>
          </template>
          <template is="dom-if" if="[[!_hideDeletedComment(_expandedDeletedComments, comment)]]">
            <template is="dom-if" if="[[_showDiff(comment)]]">
              <div class="issue-diff">
                <template is="dom-repeat" items="[[comment.amendments]]" as="delta">
                  <strong>[[delta.fieldName]]:</strong>
                  <template
                    is="dom-repeat"
                    items="[[_issuesForAmendment(delta, projectName)]]"
                    as="issue"
                  >
                    <mr-bug-link
                      project-name="[[projectName]]"
                      issue="[[issue.issue]]"
                      text="[[issue.text]]"
                    ></mr-bug-link>
                  </template>
                  <template is="dom-if" if="[[!_amendmentHasIssueRefs(delta.fieldName)]]">
                    [[delta.newOrDeltaValue]]
                  </template>
                  <template is="dom-if" if="[[delta.oldValue]]">
                    (was: [[delta.oldValue]])
                  </template>
                  <br>
                </template>
                <template is="dom-if" if="[[comment.descriptionNum]]">
                  Description was changed.
                </template>
              </div><br>
            </template>
            <div>
              <template is="dom-repeat" items="[[comment.attachments]]" as="attachment">
                <div class="comment-attachment">
                  <template is="dom-if" if="[[comment.canDelete]]">
                    <div class="attachment-delete">
                      <chops-button
                        class="attachment-delete-button"
                        on-click="_deleteAttachment"
                        data-attachment-id\$="[[attachment.attachmentId]]"
                        data-project-name\$="[[comment.projectName]]"
                        data-local-id\$="[[comment.localId]]"
                        data-sequence-num\$="[[comment.sequenceNum]]"
                        data-mark-deleted\$="[[!attachment.isDeleted]]"
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
              </template>
            </div>
            <mr-comment-content
              hidden\$="[[comment.descriptionNum]]"
              content="[[comment.content]]"
              is-deleted="[[comment.isDeleted]]"
            ></mr-comment-content>
          </template>
        </div>
      </template>
      <template is="dom-if" if="[[_shouldOfferEdit(issuePermissions)]]">
        <slot></slot>
      </template>
    `;
  }

  static get is() {
    return 'mr-comments';
  }

  static get properties() {
    return {
      commentsShownCount: {
        type: Number,
        value: 2,
      },
      comments: {
        type: Array,
        value: [],
      },
      headingLevel: {
        type: Number,
        value: 4,
      },
      projectName: String,
      issuePermissions: Object,
      _commentsHidden: {
        type: Boolean,
        value: true,
      },
      _commentsHiddenCount: {
        type: Number,
        computed: '_computeCommentsHiddenCount(commentsShownCount, comments.length)',
      },
      _hideToggle: {
        type: Boolean,
        value: false,
        computed: '_computeHideToggle(_commentsHiddenCount)',
      },
      _expandedDeletedComments: {
        type: Object,
        value: {},
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      projectName: state.projectName,
      issuePermissions: state.issuePermissions,
    };
  }

  _deleteComment(comment) {
    const issueRef = {
      projectName: comment.projectName,
      localId: comment.localId,
    };
    window.prpcClient.call('monorail.Issues', 'DeleteIssueComment', {
      issueRef,
      sequenceNum: comment.sequenceNum,
      delete: comment.isDeleted === undefined,
    }).then((resp) => {
      actionCreator.fetchComments(this.dispatchAction.bind(this), {issueRef});
    });
  }

  _flagComment(comment) {
    const issueRef = {
      projectName: comment.projectName,
      localId: comment.localId,
    };
    window.prpcClient.call('monorail.Issues', 'FlagComment', {
      issueRef,
      sequenceNum: comment.sequenceNum,
      flag: comment.isSpam === undefined,
    }).then((resp) => {
      actionCreator.fetchComments(this.dispatchAction.bind(this), {issueRef});
    });
  }

  _toggleHideDeletedComment(comment) {
    const expandedComments = Object.assign({}, this._expandedDeletedComments);
    expandedComments[comment.sequenceNum] = !expandedComments[comment.sequenceNum];
    this._expandedDeletedComments = expandedComments;
  }

  _offerCommentOptions(comment) {
    return comment.canDelete || comment.canFlag;
  }

  _canExpandDeletedComment(comment) {
    return ((comment.isSpam && comment.canFlag)
            || (comment.isDeleted && comment.canDelete));
  }

  _hideDeletedComment(expandedDeletedComments, comment) {
    return (comment.isDeleted
            && !expandedDeletedComments[comment.sequenceNum]);
  }

  _getCommentOptions(expandedDeletedComments, comment) {
    const options = [];
    if (this._canExpandDeletedComment(comment)) {
      const expanded = expandedDeletedComments[comment.sequenceNum];
      const text = (expanded ? 'Hide' : 'Show') + ' comment content';
      options.push({
        url: '#',
        text: text,
        handler: this._toggleHideDeletedComment.bind(this, comment),
      });
      options.push({separator: true});
    }
    if (comment.canDelete) {
      const text = (comment.isDeleted ? 'Undelete' : 'Delete') + ' comment';
      options.push({
        url: '#',
        text: text,
        handler: this._deleteComment.bind(this, comment),
      });
    }
    if (comment.canFlag) {
      const text = (comment.isSpam ? 'Unflag' : 'Flag') + ' comment';
      options.push({
        url: '#',
        text: text,
        handler: this._flagComment.bind(this, comment),
      });
    }
    return options;
  }

  toggleComments() {
    this._commentsHidden = !this._commentsHidden;
  }

  _amendmentHasIssueRefs(fieldName) {
    return ISSUE_REF_FIELD_NAMES.includes(fieldName);
  }

  _issuesForAmendment(delta, projectName) {
    if (!this._amendmentHasIssueRefs(delta.fieldName)
        || !delta.newOrDeltaValue) {
      return [];
    }
    // TODO(ehmaldonado): Request the issue to check for permissions and display
    // the issue summary.
    return delta.newOrDeltaValue.split(' ').map((issueRef) => {
      const matches = issueRef.match(ISSUE_ID_REGEX);
      return {
        issue: {
          projectName: matches[1] ? matches[1] : projectName,
          localId: matches[2],
          // Link all issues to the approval page.
          approvalValues: true,
        },
        text: issueRef,
      };
    });
  }

  _computeCommentHidden(commentsHidden, commentsHiddenCount, index) {
    return commentsHidden && index < commentsHiddenCount;
  }

  _computeCommentsHiddenCount(shownCount, numComments) {
    return Math.max(numComments - shownCount, 0);
  }

  _computeHideToggle(hiddenCount) {
    return hiddenCount <= 0;
  }

  _computeCommentToggleVerb(commentsHidden) {
    return commentsHidden ? 'Show' : 'Hide';
  }

  _pluralize(count, baseWord, pluralWord) {
    pluralWord = pluralWord || `${baseWord}s`;
    return count == 1 ? baseWord : pluralWord;
  }

  _showDiff(comment) {
    return comment.descriptionNum || comment.amendments;
  }

  _shouldOfferEdit(issuePermissions) {
    return (issuePermissions || []).includes(ISSUE_EDIT_PERMISSION);
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

  _isVideo(contentType) {
    return contentType.startsWith('video/');
  }

  _deleteAttachment(e) {
    const issueRef = {
      projectName: e.target.dataset.projectName,
      localId: Number.parseInt(e.target.dataset.localId),
    };

    const promise = window.prpcClient.call(
      'monorail.Issues', 'DeleteAttachment',
      {
        issueRef,
        sequenceNum: Number.parseInt(e.target.dataset.sequenceNum),
        attachmentId: Number.parseInt(e.target.dataset.attachmentId),
        delete: (e.target.dataset.markDeleted !== undefined),
      });

    promise.then(() => {
      actionCreator.fetchComments(this.dispatchAction.bind(this), {issueRef});
    }, (error) => {
      console.log('Failed to (un)delete attachment', error);
    });
  }
}
customElements.define(MrComments.is, MrComments);
