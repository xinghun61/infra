// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import 'elements/framework/mr-comment-content/mr-description.js';
import '../mr-comment-list/mr-comment-list.js';
import '../metadata/mr-edit-metadata/mr-edit-issue.js';
import {commentListToDescriptionList} from 'elements/shared/converters.js';

/**
 * `<mr-issue-details>`
 *
 * This is the main details section for a given issue.
 *
 */
export class MrIssueDetails extends connectStore(LitElement) {
  static get styles() {
    return css`
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
    `;
  }

  render() {
    return html`
      <mr-description .descriptionList=${this._descriptions}></mr-description>
      <mr-comment-list
        headingLevel="2"
        .comments=${this.comments}
        .commentsShownCount=${this.commentsShownCount}
      >
        <mr-edit-issue></mr-edit-issue>
      </mr-comment-list>
    `;
  }

  static get properties() {
    return {
      comments: {type: Array},
      commentsShownCount: {type: Number},
      _descriptions: {type: Array},
    };
  }

  constructor() {
    super();
    this.comments = [];
    this._descriptions = [];
  }

  stateChanged(state) {
    const commentsByApproval = issue.commentsByApprovalName(state);
    if (commentsByApproval && commentsByApproval.has('')) {
      // Comments without an approval go into the main view.
      const comments = commentsByApproval.get('');
      this.comments = comments.slice(1);
      this._descriptions = commentListToDescriptionList(comments);
    }
  }
}
customElements.define('mr-issue-details', MrIssueDetails);
