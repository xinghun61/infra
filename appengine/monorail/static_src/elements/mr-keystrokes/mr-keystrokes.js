// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {PolymerElement, html} from '@polymer/polymer';
import page from 'page';
import qs from 'qs';
import Mousetrap from 'mousetrap';

import {ReduxMixin} from '../redux/redux-mixin.js';
import * as issue from '../redux/issue.js';


/**
 * `<mr-keystrokes>`
 *
 * Adds keybindings for Monorail, including a dialog for showing keystrokes.
 *
 */
export class MrKeystrokes extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style>
        dialog {
          contain: layout;
          z-index: 200;
          position: fixed;
          top: 5%;
          left: 4%;
          right: 4%;
          max-height: 90%;
          border: 0;
          background: hsla(0, 0%, 0%, 0.85);
          text-shadow: #000 1px 1px 7px;
          color: white;
          padding: 1em;
          width: 90%;
          max-width: 1200px;
          font-size: var(--chops-main-font-size);
        }
        h2 {
          margin-top: 0;
          display: flex;
          justify-content: space-between;
          font-weight: normal;
          border-bottom: 2px solid white;
          font-size: var(--chops-large-font-size);
          padding-bottom: 0.5em;
        }
        .close-button {
          border: 0;
          background: 0;
          color: yellow;
          text-decoration: underline;
          cursor: pointer;
        }
        .keyboard-help {
          display: flex;
          align-items: flex-start;
          justify-content: space-around;
          flex-direction: row;
          border-bottom: 2px solid white;
          flex-wrap: wrap;
        }
        .keyboard-help-section {
          width: 32%;
          display: grid;
          grid-template-columns: 30% 70%;
          padding-bottom: 1em;
          grid-gap: 4px;
          min-width: 300px;
        }
        .help-title {
          color: yellow;
          font-weight: bold;
        }
        .key-shortcut {
          text-align: right;
          padding-right: 8px;
          font-weight: bold;
        }
        .key-name {
          color: #8d0;
        }
      </style>
      <dialog open\$="[[opened]]">
        <h2>
          Issue tracker keyboard shortcuts
          <button class="close-button" on-click="closeDialog">
            Close
          </button>
        </h2>
        <div class="keyboard-help">
          <template is="dom-repeat" items="[[shortcutDocGroups]]" as="group">
            <div class="keyboard-help-section">
              <span></span><span class="help-title">[[group.title]]</span>
                <template
                  is="dom-repeat"
                  items="[[group.keyDocs]]"
                  as="keyDoc"
                >
                  <span class="key-shortcut">
                    <template
                      is="dom-repeat"
                      items="[[keyDoc.keys]]"
                      as="key">
                      <span class="key-name">[[key]]</span>
                      <span
                        class="key-separator"
                        hidden\$="[[_isLastItem(keyDoc.keys.length, index)]]"
                      > / </span>
                    </template>:
                  </span>
                  <span class="key-tip">[[keyDoc.tip]]</span>
                </template>
            </template>
          </div>
        </template>
        <p>
          Note: Only signed in users can star issues or add comments, and
          only project members can select issues for bulk edits.
        </p>
      </dialog>
    `;
  }

  static get is() {
    return 'mr-keystrokes';
  }

  static get properties() {
    return {
      shortcutDocGroups: {
        type: Array,
        value: [
          {
            title: 'Issue list',
            keyDocs: [
              {
                keys: ['k', 'j'],
                tip: 'up/down in the list',
              },
              {
                keys: ['o', '<Enter>'],
                tip: 'open the current issue',
              },
              {
                keys: ['Shift-O'],
                tip: 'open issue in new tab',
              },
              {
                keys: ['x'],
                tip: 'select the current issue',
              },
            ],
          },
          {
            title: 'Issue details',
            keyDocs: [
              {
                keys: ['k', 'j'],
                tip: 'prev/next issue in list',
              },
              {
                keys: ['u'],
                tip: 'up to issue list',
              },
              {
                keys: ['r'],
                tip: 'reply to current issue',
              },
            ],
          },
          {
            title: 'Anywhere',
            keyDocs: [
              {
                keys: ['/'],
                tip: 'focus on the issue search field',
              },
              {
                keys: ['c'],
                tip: 'compose a new issue',
              },
              {
                keys: ['s'],
                tip: 'star the current issue',
              },
              {
                keys: ['?'],
                tip: 'show this help dialog',
              },
            ],
          },
        ],
      },
      opened: {
        type: Boolean,
        value: false,
      },
      issueEntryUrl: String,
      projectName: String,
      issueId: Number,
      issuePermissions: Array,
      queryParams: Object,
      _isStarred: Boolean,
      _fetchingIsStarred: Boolean,
      _starringIssue: Boolean,
    };
  }

  static mapStateToProps(state, element) {
    return {
      issuePermissions: state.issuePermissions,
      _isStarred: state.isStarred,
      _fetchingIsStarred: state.requests.fetchIsStarred.requesting,
      _starringIssue: state.requests.starIssue.requesting,
    };
  }

  static get observers() {
    return [
      'bindProjectKeys(projectName, issueEntryUrl)',
      `bindIssueDetailKeys(projectName, issueId, issuePermissions,
        queryParams)`,
    ];
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.unbindProjectKeys();
    this.unbindIssueDetailKeys();
  }

  toggleDialog() {
    this.opened = !this.opened;
  }

  openDialog() {
    this.opened = true;
  }

  closeDialog() {
    this.opened = false;
  }

  bindProjectKeys(projectName, issueEntryUrl) {
    this.unbindProjectKeys();

    if (!projectName) return;

    issueEntryUrl = issueEntryUrl || `/p/${projectName}/issues/entry`;

    Mousetrap.bind('/', (e) => {
      e.preventDefault();
      // Focus search.
      this.dispatchEvent(new CustomEvent('focus-search',
        {composed: true, bubbles: true}));
    });

    Mousetrap.bind('?', () => {
      // Toggle key help.
      this.toggleDialog();
    });

    Mousetrap.bind('esc', () => {
      // Close key help dialog if open.
      this.closeDialog();
    });

    Mousetrap.bind('c', () => page(issueEntryUrl));
  }

  unbindProjectKeys() {
    Mousetrap.unbind('/');
    Mousetrap.unbind('?');
    Mousetrap.unbind('esc');
    Mousetrap.unbind('c');
  }

  bindIssueDetailKeys(projectName, issueId, issuePermissions, queryParams) {
    this.unbindIssueDetailKeys();

    if (!projectName || !issueId) return;

    const queryString = qs.stringify(queryParams);
    const projectHomeUrl = `/p/${projectName}`;

    issuePermissions = issuePermissions || [];

    // TODO(zhangtiff): Update these links when mr-flipper's async request
    // finishes.
    const listUrl = `${projectHomeUrl}/issues/detail/list?${queryString}`;
    const prevUrl = `${projectHomeUrl}/issues/detail/previous?${queryString}`;
    const nextUrl = `${projectHomeUrl}/issues/detail/next?${queryString}`;
    const canComment = issuePermissions.includes('addissuecomment');
    const canStar = issuePermissions.includes('setstar');


    if (prevUrl) {
      // Previous issue in list.
      Mousetrap.bind('k', () => page(prevUrl));
    }

    if (nextUrl) {
      // Next issue in list.
      Mousetrap.bind('j', () => page(nextUrl));
    }

    if (listUrl) {
      // Back to list.
      Mousetrap.bind('u', () => page(listUrl));
    }

    if (canComment) {
      // Navigate to the form to make changes.
      // TODO(zhangtiff): Make this keystroke work even when the URL is
      // already set to #makechanges.
      Mousetrap.bind('r', (e) => {
        e.preventDefault();
        page('#makechanges');
      });
    }

    if (canStar) {
      Mousetrap.bind('s', () => {
        // Star an issue.
        if (!this._fetchingIsStarred && !this._starringIssue) {
          const newIsStarred = !this._isStarred;
          const issueRef = {
            projectName: this.projectName,
            localId: this.issueId,
          };

          this.dispatchAction(issue.star(issueRef, newIsStarred));
        }
      });
    }
  }

  unbindIssueDetailKeys() {
    Mousetrap.unbind('k');
    Mousetrap.unbind('j');
    Mousetrap.unbind('u');
    Mousetrap.unbind('r');
    Mousetrap.unbind('s');
  }

  // TODO(zhangtiff): Remove this when we migrate to lit-element.
  _isLastItem(length, index) {
    return length - 1 === index;
  }
}

customElements.define(MrKeystrokes.is, MrKeystrokes);
