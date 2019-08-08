// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import qs from 'qs';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as ui from 'elements/reducers/ui.js';
import * as user from 'elements/reducers/user.js';
import * as sitewide from 'elements/reducers/sitewide.js';
import AutoRefreshPrpcClient from 'prpc.js';
import 'elements/issue-detail/mr-comment-list/mr-comment-list.js';
import 'elements/framework/mr-comment-content/mr-description.js';
// eslint-disable-next-line max-len
import 'elements/issue-detail/dialogs/mr-edit-description/mr-edit-description.js';
import {prpcClient} from 'prpc-client-instance.js';

/**
 * `<ezt-comments>`
 *
 * Displays comments on the EZT page.
 *
 */
export class EztComments extends connectStore(LitElement) {
  static get styles() {
    return css`
      :host([codeFont]) {
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
    `;
  }

  render() {
    return html`
      <mr-description
        .descriptionList=${this.descriptionList}
      ></mr-description>
      <div class="comments">
        <mr-comment-list
          .comments=${this.commentList}
          commentsShownCount="100"
        ></mr-comment-list>
      </div>
      <mr-edit-description id="edit-description"></mr-edit-description>
    `;
  }

  static get properties() {
    return {
      issueId: {type: Number},
      projectName: {type: String},
      prefs: {type: Object},
      commentList: {type: Array},
      descriptionList: {type: Array},
      codeFont: {
        type: Boolean,
        reflect: true,
      },
    };
  }

  constructor() {
    super();
    this.prefs = {};
    this.commentList = [];
    this.descriptionList = [];
  }

  stateChanged(state) {
    this.prefs = user.prefs(state);

    const updatedComments = issue.comments(state);
    if (updatedComments && updatedComments.length) {
      const commentList = [];
      const descriptionList = [];

      updatedComments.forEach((comment) => {
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
  }

  update(changedProperties) {
    if (changedProperties.has('prefs')) {
      this.codeFont = this.prefs['code_font'] === 'true';
    }
    super.update(changedProperties);
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
    // Make flipper still work in legazy EZT page.
    const params = qs.parse(window.location.search.substr(1));
    if (params) {
      store.dispatch(sitewide.setQueryParams(params));
    }

    const hash = window.location.hash.substr(1);
    if (hash) {
      store.dispatch(ui.setFocusId(hash));
    }
  }

  initializeState() {
    if (!prpcClient) {
      // prpcClient is not defined yet, but we need it to fetch the
      // comment references for autocomplete.
      prpcClient = new AutoRefreshPrpcClient(
          window.CS_env.token, window.CS_env.tokenExpiresSec);
    }

    const allComments = [this.descriptionList[0]].concat(this.commentList);
    // mr-comment-content relies on projectName being set on the redux state.
    store.dispatch(issue.setIssueRef(this.issueId, this.projectName));
    store.dispatch({
      type: issue.FETCH_COMMENTS_SUCCESS,
      comments: allComments,
    });
    store.dispatch(user.fetchPrefs());
    store.dispatch(issue.fetchCommentReferences(
        allComments, this.projectName));
  }
}
customElements.define('ezt-comments', EztComments);
