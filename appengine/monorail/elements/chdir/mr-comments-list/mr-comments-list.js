/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import '../../../node_modules/@polymer/polymer/polymer-legacy.js';
import {html} from '../../../node_modules/@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '../../../node_modules/@polymer/polymer/polymer-element.js';
/**
 * `<mr-comments-list>`
 *
 * The list of comments for a Monorail Polymer profile.
 *
 */
export class MrCommentList extends PolymerElement {
  static get template() {
    return html`
      <style>
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
          font-size: 90%;
          font-weight: normal;
          text-align: left;
          margin: 0 auto;
          padding: 2em 1em;
          height: 20px;
        }
        td {
          background: #f8f8f8;
          padding: 4px;
          padding-left: 8px;
          text-overflow: ellipsis;
        }
        th {
          text-decoration: none;
          margin-right: 0;
          padding-right: 0;
          padding-left: 8px;
          white-space: nowrap;
          background: #e3e9ff;
          text-align: left;
          border-right: 1px solid #fff;
          border-top: 1px solid #fff;
        }
      </style>
      <table cellspacing="0" cellpadding="0">
        <tbody>
           <tr id="heading-row">
            <th style="width:20%;">Date</th>
            <th style="width:10%;">Project</th>
            <th style="width:50%;">Comment</th>
            <th style="width:20%;">Issue Link</th>
          </tr>

          <template is="dom-repeat" items="[[displayedComments]]" as="comment">
            <tr id="row">
              <td style="width:20%;"><chops-timestamp timestamp="[[comment.timestamp]]" short=""></chops-timestamp></td>
              <td style="width:10%;">[[comment.projectName]]</td>
              <td class="ellipsis" style="width:50%;">[[_truncateMessage(comment.content)]]</td>
              <td style="width:20%;">
                <a href\$="/p/[[comment.projectName]]/issues/detail?id=[[comment.localId]]">
                  Issue [[comment.localId]]
                </a>
              </td>
            </tr>
          </template>
          <template is="dom-if" if="[[_checkIfCommentsEmpty(displayedComments)]]">
            <tr>
              <td colspan="4"><i>No comments.</i></td>
            </tr>
          </template>
        </tbody>
      </table>
    `;
  }

  static get is() {
    return 'mr-comments-list';
  }

  static get properties() {
    return {
      user: {
        type: String,
      },
      displayedComments: {
        type: Array,
        computed: '_computedComments(selectedDate, comments)',
        value: [],
      },
      viewedUserId: {
        type: Number,
      },
      comments: {
        type: Array,
        notify: true,
        value: [],
      },
      selectedDate: {
        type: Number,
        notify: true,
      },
    };
  }

  _truncateMessage(message) {
    return message && message.substring(0, message.indexOf('\n'));
  }

  _computedComments(selectedDate, comments) {
    if (selectedDate == undefined) {
      return comments;
    } else {
      let computedComments = [];
      if (comments == undefined) {
        return computedComments;
      }
      for (let i = 0; i < comments.length; i++) {
        if (comments[i].timestamp <= selectedDate &&
           comments[i].timestamp >= (selectedDate - 86400)) {
          computedComments.push(comments[i]);
        }
      }
      return computedComments;
    }
  }

  _checkIfCommentsEmpty(displayedComments) {
    return !displayedComments || displayedComments.length === 0;
  }
}
customElements.define(MrCommentList.is, MrCommentList);
