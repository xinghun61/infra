// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import 'elements/framework/mr-comment-content/mr-comment-content.js';
import 'elements/chops/chops-timestamp/chops-timestamp.js';

/**
 * `<mr-comment-table>`
 *
 * The list of comments for a Monorail Polymer profile.
 *
 */
export class MrCommentTable extends LitElement {
  static get styles() {
    return css`
      .ellipsis {
        max-width: 50%;
        text-overflow: ellipsis;
        overflow: hidden;
        white-space: nowrap;
      }
      table {
        word-wrap: break-word;
        width: 100%;
      }
      tr {
        font-size: var(--chops-main-font-size);
        font-weight: normal;
        text-align: left;
        line-height: 180%;
      }
      td, th {
        border-bottom: var(--chops-normal-border);
        padding: 0.25em 16px;
      }
      td {
        text-overflow: ellipsis;
      }
      th {
        text-align: left;
      }
      .no-wrap {
        white-space: nowrap;
      }
    `;
  }

  render() {
    const comments = this._displayedComments(this.selectedDate, this.comments);
    // TODO(zhangtiff): render deltas for comment changes.
    return html`
      <table cellspacing="0" cellpadding="0">
        <tbody>
           <tr id="heading-row">
            <th>Date</th>
            <th>Project</th>
            <th>Comment</th>
            <th>Issue Link</th>
          </tr>

          ${comments && comments.length ? comments.map((comment) => html`
            <tr id="row">
              <td class="no-wrap">
                <chops-timestamp
                  .timestamp=${comment.timestamp}
                  short
                ></chops-timestamp>
              </td>
              <td>${comment.projectName}</td>
              <td class="ellipsis">
                <mr-comment-content
                  .content=${this._truncateMessage(comment.content)}
                ></mr-comment-content>
              </td>
              <td class="no-wrap">
                <a href="/p/${comment.projectName}/issues/detail?id=${comment.localId}">
                  Issue ${comment.localId}
                </a>
              </td>
            </tr>
          `) : html`
            <tr>
              <td colspan="4"><i>No comments.</i></td>
            </tr>
          `}
        </tbody>
      </table>
    `;
  }

  static get properties() {
    return {
      comments: {type: Array},
      selectedDate: {type: Number},
    };
  }

  constructor() {
    super();
    this.comments = [];
  }

  _truncateMessage(message) {
    return message && message.substring(0, message.indexOf('\n'));
  }

  _displayedComments(selectedDate, comments) {
    if (!selectedDate) {
      return comments;
    } else {
      const computedComments = [];
      if (!comments) return computedComments;

      for (let i = 0; i < comments.length; i++) {
        if (comments[i].timestamp <= selectedDate &&
           comments[i].timestamp >= (selectedDate - 86400)) {
          computedComments.push(comments[i]);
        }
      }
      return computedComments;
    }
  }
}
customElements.define('mr-comment-table', MrCommentTable);
