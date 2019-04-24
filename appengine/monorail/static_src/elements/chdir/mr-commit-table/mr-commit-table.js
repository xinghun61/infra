// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {html} from '@polymer/polymer/lib/utils/html-tag.js';
import {PolymerElement} from '@polymer/polymer/polymer-element.js';
import 'elements/chops/chops-timestamp/chops-timestamp.js';

/**
 * `<mr-commit-table>`
 *
 * Table that displays user's commit history.
 *
 */
export class MrCommitTable extends PolymerElement {
  static get template() {
    return html`
      <style>
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

        th:last-child { border-right: 0; }
        tr:nth-child(even) { background: #f8f8f8; }
      </style>
      <table cellspacing="0" cellpadding="0">
        <tbody>
          <tr id="headingRow">
            <th style="width:15%;">Time</th>
            <th style="width:15%;">Commit SHA</th>
            <th style="width:15%;">Repo</th>
            <th style="width:55%;">Commit Message</th>
          </tr>
          <template is="dom-repeat" items="[[displayedCommits]]" as="commit">
            <tr id="row">
              <td style="width:15%;">
                <chops-timestamp
                  timestamp="[[commit.commitTime]]"
                  short
                ></chops-timestamp>
              </td>
              <td style="width:15%;"><a class="nav-link" href\$="[[commit.commitRepoUrl]]/+/[[commit.commitSha]]">[[_truncateSHA(commit.commitSha)]]</a></td>
              <td style="width:15%;">[[_truncateRepo(commit.commitRepoUrl)]]</td>
              <td style="width:55%;">[[_truncateMessage(commit.commitMessage)]]</td>
            </tr>
          </template>
          <template is="dom-if" if="[[_checkIfCommitsEmpty(displayedCommits)]]">
            <tr>
              <td colspan="4"><i>No commits.</i></td>
            </tr>
          </template>
        </tbody>
      </table>
    `;
  }

  static get is() {
    return 'mr-commit-table';
  }

  static get properties() {
    return {
      commits: {
        type: Array,
        notify: true,
        value: [],
      },
      displayedCommits: {
        type: Array,
        computed: '_computedCommits(selectedDate, commits)',
        value: [],
      },
      commitsLoaded: {
        type: Boolean,
      },
      fetchingCommits: {
        type: Boolean,
      },
      user: {
        type: String,
      },
      selectedDate: {
        type: Number,
        notify: true,
      },
      emptyList: {
        type: Boolean,
        computed: '_checkIfCommitsEmpty(displayedCommits)',
      },
    };
  }

  _computedCommits(selectedDate, commits) {
    if (selectedDate == undefined) {
      return commits;
    } else {
      const computedCommits = [];
      if (commits == undefined) {
        return computedCommits;
      }
      for (let i = 0; i < commits.length; i++) {
        if (commits[i].commitTime <= selectedDate &&
           commits[i].commitTime >= (selectedDate - 86400)) {
          computedCommits.push(commits[i]);
        }
      }
      return computedCommits;
    }
  }

  _checkEmptyList(list) {
    if (list.length != 0) {
      return list;
    } else {
      return ['None'];
    }
  }

  _truncateSHA(sha) {
    return sha.substring(0, 6);
  }

  _checkIfCommitsEmpty(displayedCommits) {
    return !displayedCommits || displayedCommits.length === 0;
  }

  _truncateRepo(repo) {
    const url = repo.substring(8, repo.length - 1);
    const myProject = url.substring(0, url.indexOf('.'));

    const myDirectory = url.substring(url.indexOf('/') + 1, url.length);
    const myRepo = myProject + ' ' + myDirectory;
    return myRepo;
  }

  _truncateMessage(message) {
    return message.substring(0, message.indexOf('\n'));
  }
}
customElements.define(MrCommitTable.is, MrCommitTable);
