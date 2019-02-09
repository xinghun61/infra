// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';
import '../../mr-comment-content/mr-comment-content.js';
import '../mr-comments/mr-comments.js';
import '../mr-edit-metadata/mr-edit-issue.js';
import '../mr-inline-editor/mr-inline-editor.js';
import '../shared/mr-flt-styles.js';

/**
 * `<mr-issue-details>`
 *
 * This is the main details section for a given issue.
 *
 */
export class MrIssueDetails extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-flt-styles">
        :host {
          font-size: 85%;
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
        .comments-section{
          box-sizing: border-box;
          padding: 0.25em 8px;
        }
      </style>
      <mr-inline-editor
        id="editDescription"
        heading-level="2"
        content="[[_description.content]]"
        title="Feature description"
        edit-text="Edit description"
        placeholder="Feature description"
        on-save="_updateDescriptionHandler"
      >
        <mr-comment-content content="[[_description.content]]"></mr-comment-content>
      </mr-inline-editor>
      <h2 class="medium-heading" hidden\$="[[!_comments.length]]">
        Feature discussion / Changelog
      </h2>
      <mr-comments
        heading-level="3"
        comments="[[_comments]]"
        comments-shown-count="5"
        edit-permission="editissue"
      >
        <h3 id="editIssue" class="medium-heading">Add a comment and make changes</h3>
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
      </mr-comments>
    `;
  }

  static get is() {
    return 'mr-issue-details';
  }

  static get properties() {
    return {
      comments: Array,
      issueId: Number,
      projectName: String,
      _description: {
        type: String,
        computed: '_computeDescription(comments)',
      },
      _comments: {
        type: Array,
        computed: '_filterComments(comments)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      issueId: state.issueId,
      projectName: state.projectName,
      comments: state.comments,
    };
  }

  _updateDescriptionHandler(evt) {
    if (!evt || !evt.detail) return;
    const message = {
      trace: {token: this.token},
      issueRef: {
        projectName: this.projectName,
        localId: this.issueId,
      },
      commentContent: evt.detail.commentContent,
      isDescription: true,
      sendEmail: evt.detail.sendEmail,
    };

    actionCreator.updateIssue(this.dispatchAction.bind(this), message);
  }

  _filterComments(comments) {
    if (!comments || !comments.length) return [];
    return comments.filter((c) => (!c.approvalRef && c.sequenceNum));
  }

  _computeDescription(comments) {
    if (!comments || !comments.length) return {};
    for (let i = comments.length - 1; i >= 0; i--) {
      if (!comments[i].approvalRef && comments[i].descriptionNum) {
        return comments[i];
      }
    }
    return {};
  }
}
customElements.define(MrIssueDetails.is, MrIssueDetails);
