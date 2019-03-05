// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

import '../../chops/chops-button/chops-button.js';
import '../../chops/chops-timestamp/chops-timestamp.js';
import '../../mr-bug-link/mr-bug-link.js';
import '../../mr-comment-content/mr-comment-content.js';
import '../../mr-comment-content/mr-attachment.js';
import '../../mr-dropdown/mr-dropdown.js';
import '../../mr-user-link/mr-user-link.js';
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
          padding: 0.5em 8px;
          text-align: left;
          font-size: 110%;
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
          padding: 1em 0 0 0;
        }
        .comment-header {
          background: var(--chops-card-heading-bg);
          padding: 3px 1px 1px 8px;
          width: 100%;
          display: flex;
          justify-content: space-between;
          align-items: center;
          box-sizing: border-box;
        }
        .comment-options {
          float: right;
          font-size: 0.9em;
          text-align: right;
          text-decoration: none;
        }
        .comment-body {
          margin: 4px;
          box-sizing: border-box;
        }
        .deleted-comment-notice {
          color: #888;
        }
        .issue-diff {
          background: var(--chops-card-details-bg);
          display: inline-block;
          padding: 4px 8px;
          width: 100%;
          box-sizing: border-box;
        }
      </style>
      <template is="dom-if" if="[[fetchingComments]]">
        Loading comments...
      </template>
      <button on-click="toggleComments" class="toggle" hidden\$="[[_hideToggle]]">
        [[_computeCommentToggleVerb(_commentsHidden)]]
        [[_commentsHiddenCount]]
        older
        [[_pluralize(_commentsHiddenCount, 'comment')]]
      </button>
      <template is="dom-repeat" items="[[comments]]" as="comment">
        <div
          class="card-comment"
          hidden\$="[[_computeCommentHidden(_commentsHidden, _commentsHiddenCount, index)]]"
          id\$="c[[comment.sequenceNum]]"
        >
          <span
            role="heading"
            aria-level\$="[[headingLevel]]"
            class="comment-header"
          >
            <div>
              <a href\$="#c[[comment.sequenceNum]]">
                Comment [[comment.sequenceNum]]
              </a>
              by
              <mr-user-link
                display-name="[[comment.commenter.displayName]]"
                user-id="[[comment.commenter.userId]]"
              ></mr-user-link>
              on
              <chops-timestamp timestamp="[[comment.timestamp]]"></chops-timestamp>
            </div>
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
            <div class="comment-body">
              <span class="deleted-comment-notice">
                Deleted comment
              </span>
            </div>
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
            <div class="comment-body">
              <mr-comment-content
                hidden\$="[[comment.descriptionNum]]"
                content="[[comment.content]]"
                is-deleted="[[comment.isDeleted]]"
              ></mr-comment-content>
              <div hidden\$="[[comment.descriptionNum]]">
                <template is="dom-repeat" items="[[comment.attachments]]" as="attachment">
                  <mr-attachment
                    attachment="[[attachment]]"
                    project-name="[[comment.projectName]]"
                    local-id="[[comment.localId]]"
                    sequence-num="[[comment.sequenceNum]]"
                    can-delete="[[comment.canDelete]]"
                  ></mr-attachment>
                </template>
              </div>
            </div>
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
      focusId: String,
      fetchingComments: Boolean,
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

  static get observers() {
    return [
      '_onFocusIdChange(focusId, comments)',
    ];
  }

  static mapStateToProps(state, element) {
    return {
      focusId: state.focusId,
      projectName: state.projectName,
      issuePermissions: state.issuePermissions,
      fetchingComments: state.fetchingComments,
    };
  }

  _onFocusIdChange(focusId, comments) {
    if (!focusId || !comments.length) return;
    flush();
    const element = this.shadowRoot.querySelector('#' + focusId);
    if (element) {
      if (element.hidden) {
        this.toggleComments();
      }
      // TODO(ehmaldonado): Really scroll the element into view. As it is, it is
      // hidden by the page and issue headers.
      element.scrollIntoView();
    }
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
        text: text,
        handler: this._toggleHideDeletedComment.bind(this, comment),
      });
      options.push({separator: true});
    }
    if (comment.canDelete) {
      const text = (comment.isDeleted ? 'Undelete' : 'Delete') + ' comment';
      options.push({
        text: text,
        handler: this._deleteComment.bind(this, comment),
      });
    }
    if (comment.canFlag) {
      const text = (comment.isSpam ? 'Unflag' : 'Flag') + ' comment';
      options.push({
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
