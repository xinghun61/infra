// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';
import * as ui from '../../redux/ui.js';
import '../../mr-comment-content/mr-description.js';
import '../mr-comment-list/mr-comment-list.js';
import '../mr-edit-metadata/mr-edit-issue.js';
import '../../shared/mr-shared-styles.js';

/**
 * `<mr-issue-details>`
 *
 * This is the main details section for a given issue.
 *
 */
export class MrIssueDetails extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-shared-styles">
        :host {
          font-size: var(--chops-main-font-size);
          background-color: white;
          padding: 0;
          padding-bottom: 1em;
          display: flex;
          align-items: stretch;
          justify-content: flex-start;
          flex-direction: column;
          z-index: 1;
          margin: 0;
          box-sizing: border-box;
        }
        h3 {
          margin-top: 1em;
        }
        mr-description {
          margin-bottom: 1em;
        }
      </style>
      <mr-description description-list="[[_descriptionList]]"></mr-description>
      <mr-comment-list
        heading-level="2"
        comments="[[_comments]]"
        comments-shown-count="[[commentsShownCount]]"
        focused-comment="[[_focusedComment]]"
      >
        <mr-edit-issue
          id="metadataForm"
          owner-name="[[_omitEmptyDisplayName(issue.ownerRef.displayName)]]"
          cc="[[issue.ccRefs]]"
          status="[[issue.statusRef.status]]"
          statuses="[[statuses]]"
          summary="[[issue.summary]]"
          components="[[issue.componentRefs]]"
          field-defs="[[_fieldDefs]]"
          field-values="[[issue.fieldValues]]"
          blocked-on="[[issue.blockedOnIssueRefs]]"
          blocking="[[issue.blockingIssueRefs]]"
          label-names="[[_labelNames]]"
        ></mr-edit-issue>
      </mr-comment-list>
    `;
  }

  static get is() {
    return 'mr-issue-details';
  }

  static get properties() {
    return {
      comments: Array,
      commentsShownCount: Number,
      _descriptionList: {
        type: Array,
        computed: '_computeDescriptionList(comments)',
      },
      _comments: {
        type: Array,
        computed: '_filterComments(comments)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      comments: issue.comments(state),
    };
  }

  _filterComments(comments) {
    if (!comments || !comments.length) return [];
    return comments.filter((c) => (!c.approvalRef && c.sequenceNum));
  }

  _computeDescriptionList(comments) {
    if (!comments || !comments.length) return {};
    return comments.filter((comment) => {
      if (comment.approvalRef) {
        return false;
      }
      return comment.descriptionNum || !comment.sequenceNum;
    });
  }
}
customElements.define(MrIssueDetails.is, MrIssueDetails);
