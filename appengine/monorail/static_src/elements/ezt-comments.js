// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {ReduxMixin, actionType, actionCreator} from './redux/redux-mixin.js';
import AutoRefreshPrpcClient from '../prpc.js';
import './flt/mr-comment-list/mr-comment-list.js';
import './mr-comment-content/mr-description.js';
import './flt/mr-edit-description/mr-edit-description.js';

/**
 * `<ezt-comments>`
 *
 * Displays comments on the EZT page.
 *
 */
export class EztComments extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style>
        mr-description {
          display: block;
          padding: 0 12px;
          max-width: 80em;
        }
        .comments {
          margin: 1.3em 1em;
          max-width: 80em;
        }
      </style>
      <mr-description
        description-list="[[descriptionList]]"
      ></mr-description>
      <div class="comments">
        <mr-comment-list
          quick-mode="[[quickMode]]"
          comments="[[commentList]]"
          comments-shown-count="100"
        ></mr-comment-list>
      </div>
      <template is="dom-if" if="[[!quickMode]]">
        <mr-edit-description id="edit-description"></mr-edit-description>
      </template>
    `;
  }

  static get is() {
    return 'ezt-comments';
  }

  static get properties() {
    return {
      comments: {
        type: Array,
        value: [],
        observer: '_onCommentsChange',
      },
      issueId: Number,
      projectName: String,
      quickMode: {
        type: Boolean,
        value: true,
      },
      commentList: Array,
      descriptionList: Array,
      userDisplayName: String,
    };
  }

  static mapStateToProps(state, element) {
    return {
      comments: state.comments,
    };
  }

  connectedCallback() {
    super.connectedCallback();
    this._onLocationChanged();
    window.onpopstate = this._onLocationChanged.bind(this);
  }

  openEditDescriptionDialog(e) {
    this.shadowRoot.querySelector('#edit-description').open(e);
  }

  _onLocationChanged() {
    const hash = window.location.hash.substr(1);
    if (hash) {
      this.dispatchAction({
        type: actionType.SET_FOCUS_ID,
        focusId: hash,
      });
    }
  }

  _onCommentsChange(comments) {
    if (!comments || !comments.length) return;

    const commentList = [];
    const descriptionList = [];

    comments.forEach((comment) => {
      if (comment.sequenceNum) {
        commentList.push(comment);
      }
      if (comment.descriptionNum || !comment.sequenceNum) {
        descriptionList.push(comment);
      }
    });

    this.commentList = commentList;
    this.descriptionList = descriptionList;
  }

  initialize() {
    this.quickMode = false;

    if (!window.prpcClient) {
      // window.prpcClient is not defined yet, but we need it to fetch the
      // comment references for autocomplete.
      window.prpcClient = new AutoRefreshPrpcClient(
        window.CS_env.token, window.CS_env.tokenExpiresSec);
    }

    const allComments = this.commentList.concat(this.descriptionList);
    // mr-comment-content relies on projectName being set on the redux state.
    this.dispatchAction({
      type: actionType.UPDATE_ISSUE_REF,
      projectName: this.projectName,
      issueId: this.issueId,
    });
    this.dispatchAction({
      type: actionType.FETCH_COMMENTS_SUCCESS,
      comments: allComments,
    });
    actionCreator.fetchUserPrefs(
      this.dispatchAction.bind(this));
    actionCreator.fetchCommentReferences(
      this.dispatchAction.bind(this), allComments, this.projectName);
  }
}
customElements.define(EztComments.is, EztComments);
