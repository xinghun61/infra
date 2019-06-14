// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {cache} from 'lit-html/directives/cache.js';
import {LitElement, html, css} from 'lit-element';

import '../../chops/chops-button/chops-button.js';
import './mr-comment.js';
import {connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as ui from 'elements/reducers/ui.js';
import {userIsMember} from 'elements/shared/helpers.js';
import {SHARED_STYLES} from 'elements/shared/shared-styles.js';

const ADD_ISSUE_COMMENT_PERMISSION = 'addissuecomment';

/**
 * `<mr-comment-list>`
 *
 * Display a list of Monorail comments.
 *
 */
export class MrCommentList extends connectStore(LitElement) {
  constructor() {
    super();

    this.commentsShownCount = 2;
    this.comments = [];
    this.headingLevel = 4;

    this.issuePermissions = [];
    this.focusId = null;

    this.usersProjects = new Map();

    this._hideComments = true;
  }

  static get properties() {
    return {
      commentsShownCount: {type: Number},
      comments: {type: Array},
      headingLevel: {type: Number},

      issuePermissions: {type: Array},
      focusId: {type: String},

      usersProjects: {type: Object},

      _hideComments: {type: Boolean},
    };
  }

  stateChanged(state) {
    this.issuePermissions = issue.permissions(state);
    this.focusId = ui.focusId(state);
    this.usersProjects = issue.usersProjects(state);
  }

  updated(changedProperties) {
    super.updated(changedProperties);

    if (!this._hideComments) return;

    // If any hidden comment is focused, show all hidden comments.
    const hiddenCount =
      _hiddenCount(this.comments.length, this.commentsShownCount);
    const hiddenComments = this.comments.slice(0, hiddenCount);
    for (const comment of hiddenComments) {
      if ('c' + comment.sequenceNum === this.focusId) {
        this._hideComments = false;
        break;
      }
    };
  }

  static get styles() {
    return [SHARED_STYLES, css`
      button.toggle {
        background: none;
        color: var(--chops-link-color);
        border: 0;
        border-bottom: var(--chops-normal-border);
        border-top: var(--chops-normal-border);
        width: 100%;
        padding: 0.5em 8px;
        text-align: left;
        font-size: var(--chops-main-font-size);
      }
      button.toggle:hover {
        cursor: pointer;
        text-decoration: underline;
      }
      button.toggle[hidden] {
        display: none;
      }
      .edit-slot {
        margin-top: 3em;
      }
    `];
  }

  render() {
    const hiddenCount =
      _hiddenCount(this.comments.length, this.commentsShownCount);
    return html`
      <button @click=${this._toggleHide}
          class="toggle"
          ?hidden=${hiddenCount <= 0}>
        ${this._hideComments ? 'Show' : 'Hide'}
        ${hiddenCount}
        older
        ${hiddenCount == 1 ? 'comment' : 'comments'}
      </button>
      ${cache(this._hideComments ? '' :
    html`${this.comments.slice(0, hiddenCount).map(
      this.renderComment.bind(this))}`)}
      ${this.comments.slice(hiddenCount).map(this.renderComment.bind(this))}
      <div class="edit-slot"
          ?hidden=${!_canAddComment(this.issuePermissions)}>
        <slot></slot>
      </div>
    `;
  }

  renderComment(comment) {
    const commenterIsMember = userIsMember(
      comment.commenter, comment.projectName, this.usersProjects);
    return html`
      <mr-comment
          .comment=${comment}
          headingLevel=${this.headingLevel}
          ?highlighted=${'c' + comment.sequenceNum === this.focusId}
          ?commenterIsMember=${commenterIsMember}
      ></mr-comment>`;
  }

  _toggleHide() {
    this._hideComments = !this._hideComments;
  }
}

function _hiddenCount(commentCount, commentsShownCount) {
  return Math.max(commentCount - commentsShownCount, 0);
}

function _canAddComment(issuePermissions) {
  return (issuePermissions || []).includes(ADD_ISSUE_COMMENT_PERMISSION);
}

customElements.define('mr-comment-list', MrCommentList);
