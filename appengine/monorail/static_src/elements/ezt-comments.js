// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {ReduxMixin} from './redux/redux-mixin.js';
import * as issue from './redux/issue.js';
import * as ui from './redux/ui.js';
import * as user from './redux/user.js';
import AutoRefreshPrpcClient from '../prpc.js';
import './flt/mr-comment-list/mr-comment-list.js';
import './mr-comment-content/mr-description.js';
import './flt/dialogs/mr-edit-description.js';

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
        :host([code-font]) {
          --mr-toggled-font-family: monospace;
        }
        mr-description {
          display: block;
          padding: 8px 12px;
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
      prefs: Object,
      quickMode: {
        type: Boolean,
        value: true,
      },
      commentList: Array,
      descriptionList: Array,
      userDisplayName: String,
      codeFont: {
        type: Boolean,
        computed: '_computeCodeFont(prefs)',
        reflectToAttribute: true,
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      comments: issue.comments(state),
      prefs: user.user(state).prefs,
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

  _computeCodeFont(prefs) {
    if (!prefs) return false;
    return prefs.get('code_font') === 'true';
  }

  _onLocationChanged() {
    const hash = window.location.hash.substr(1);
    if (hash) {
      this.dispatchAction(ui.setFocusId(hash));
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

    const allComments = [this.descriptionList[0]].concat(this.commentList);
    // mr-comment-content relies on projectName being set on the redux state.
    this.dispatchAction(issue.setIssueRef(this.issueId, this.projectName));
    this.dispatchAction({
      type: issue.FETCH_COMMENTS_SUCCESS,
      comments: allComments,
    });
    this.dispatchAction(user.fetchPrefs());
    this.dispatchAction(issue.fetchCommentReferences(
      allComments, this.projectName));
  }
}
customElements.define(EztComments.is, EztComments);
