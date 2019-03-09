// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';

import '../../chops/chops-button/chops-button.js';
import '../../chops/chops-timestamp/chops-timestamp.js';
import '../../mr-bug-link/mr-bug-link.js';
import '../../mr-comment-content/mr-comment-content.js';
import '../../mr-comment-content/mr-attachment.js';
import '../../mr-dropdown/mr-dropdown.js';
import '../../mr-user-link/mr-user-link.js';

// Match: projectName:localIdFormat
const ISSUE_ID_REGEX = /(?:-?([a-z0-9-]+):)?(\d+)/i;
const ISSUE_REF_FIELD_NAMES = [
  'Blocking',
  'Blockedon',
  'Mergedinto',
];

/**
 * `<mr-comment>`
 *
 * A component for an individual comment.
 *
 */
export class MrComment extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style>
        :host {
          display: block;
          margin: 1.5em 0 0 0;
        }
        :host([highlighted]) {
          /* TODO(zhangtiff): Come up with a better highlighted style. */
          border: 1px solid var(--chops-primary-accent-color);
        }
        :host([hidden]) {
          display: none;
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
      <span
        role="heading"
        aria-level\$="[[headingLevel]]"
        class="comment-header"
      >
        <div>
          <a href\$="#[[id]]">
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
              items="[[_getCommentOptions(_isExpandedIfDeleted, comment)]]"
              icon="more_vert"
            ></mr-dropdown>
          </div>
        </template>
      </span>
      <template is="dom-if" if="[[_hideDeletedComment(_isExpandedIfDeleted, comment)]]">
        <div class="comment-body">
          <span class="deleted-comment-notice">
            Deleted comment
          </span>
        </div>
      </template>
      <template is="dom-if" if="[[!_hideDeletedComment(_isExpandedIfDeleted, comment)]]">
        <template is="dom-if" if="[[_showDiff(comment)]]">
          <div class="issue-diff">
            <template is="dom-repeat" items="[[comment.amendments]]" as="delta">
              <strong>[[delta.fieldName]]:</strong>
              <template
                is="dom-repeat"
                items="[[_issuesForAmendment(delta, comment.projectName)]]"
                as="issue"
              >
                <mr-bug-link
                  project-name="[[comment.projectName]]"
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
    `;
  }

  static get is() {
    return 'mr-comment';
  }

  static get properties() {
    return {
      comment: Object,
      focusId: String,
      headingLevel: String,
      id: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeId(comment.sequenceNum)',
      },
      highlighted: {
        type: String,
        reflectToAttribute: true,
        computed: '_computeIsHighlighted(id, focusId)',
        observer: '_onHighlight',
      },
      _isExpandedIfDeleted: Boolean,
    };
  }

  _computeId(sequenceNum) {
    if (!sequenceNum) return;
    return `c${sequenceNum}`;
  }

  _computeIsHighlighted(id, focusId) {
    if (!id || !focusId) return;
    return id === focusId;
  }

  _onHighlight(highlighted) {
    if (highlighted) {
      // TODO(zhangtiff): Revisit this logic once we've upgraded to LitElement
      // and have more lifecycle functions to work with.
      window.requestAnimationFrame(() => {
        this.dispatchEvent(new CustomEvent('expand-parent', {
          bubbles: true,
          composed: true,
          detail: {
            // TODO(zhangtiff): See if we can somehow redesign this logic to
            // not require redundant scrollIntoViews.
            callback: () => {
              this.scrollIntoView();
            },
          },
        }));
        this.scrollIntoView();
      });
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

  _toggleHideDeletedComment() {
    this._isExpandedIfDeleted = !this._isExpandedIfDeleted;
  }

  _offerCommentOptions(comment) {
    return comment.canDelete || comment.canFlag;
  }

  _canExpandDeletedComment(comment) {
    return ((comment.isSpam && comment.canFlag)
            || (comment.isDeleted && comment.canDelete));
  }

  _hideDeletedComment(isExpandedIfDeleted, comment) {
    return comment.isDeleted && !isExpandedIfDeleted;
  }

  _getCommentOptions(isExpandedIfDeleted, comment) {
    const options = [];
    if (this._canExpandDeletedComment(comment)) {
      const text = (isExpandedIfDeleted ? 'Hide' : 'Show') + ' comment content';
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

  _showDiff(comment) {
    return comment.descriptionNum || comment.amendments;
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
customElements.define(MrComment.is, MrComment);
