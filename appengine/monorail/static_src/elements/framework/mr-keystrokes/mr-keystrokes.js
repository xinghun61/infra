// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import qs from 'qs';
import Mousetrap from 'mousetrap';

import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {issueRefToString} from '../../shared/converters';


const SHORTCUT_DOC_GROUPS = [
  {
    title: 'Issue list',
    keyDocs: [
      {
        keys: ['k', 'j'],
        tip: 'up/down in the list',
      },
      {
        keys: ['o', 'Enter'],
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
];

/**
 * `<mr-keystrokes>`
 *
 * Adds keybindings for Monorail, including a dialog for showing keystrokes.
 *
 */
export class MrKeystrokes extends connectStore(LitElement) {
  static get styles() {
    return css`
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
        grid-template-columns: 40% 60%;
        padding-bottom: 1em;
        grid-gap: 4px;
        min-width: 300px;
      }
      .help-title {
        font-weight: bold;
      }
      .key-shortcut {
        text-align: right;
        padding-right: 8px;
        font-weight: bold;
        margin: 2px;
      }
      kbd {
        background: var(--chops-gray-200);
        padding: 2px 8px;
        border-radius: 2px;
        min-width: 28px;
      }
    `;
  }

  render() {
    return html`
      <chops-dialog ?opened=${this.opened}>
        <h2>
          Issue tracker keyboard shortcuts
          <button class="close-button" @click=${this.closeDialog}>
            Close
          </button>
        </h2>
        <div class="keyboard-help">
          ${this.shortcutDocGroups.map((group) => html`
            <div class="keyboard-help-section">
              <span></span><span class="help-title">${group.title}</span>
              ${group.keyDocs.map((keyDoc) => html`
                <span class="key-shortcut">
                  ${keyDoc.keys.map((key, i) => html`
                    <kbd>${key}</kbd>
                    <span
                      class="key-separator"
                      ?hidden=${i === keyDoc.keys.length - 1}
                    > / </span>
                  `)}:
                </span>
                <span class="key-tip">${keyDoc.tip}</span>
              `)}
            </div>
          `)}
        </div>
        <p>
          Note: Only signed in users can star issues or add comments, and
          only project members can select issues for bulk edits.
        </p>
      </chops-dialog>
    `;
  }

  static get properties() {
    return {
      shortcutDocGroups: {type: Array},
      opened: {type: Boolean},
      issueEntryUrl: {type: String},
      projectName: {type: String},
      issueId: {type: Number},
      issuePermissions: {type: Array},
      queryParams: {type: Object},
      _isStarred: {type: Boolean},
      _fetchingIsStarred: {type: Boolean},
      _starringIssue: {type: Boolean},
    };
  }

  constructor() {
    super();

    this.shortcutDocGroups = SHORTCUT_DOC_GROUPS;
    this.opened = false;
  }

  stateChanged(state) {
    this.issuePermissions = issue.permissions(state);
    // Create an issue ref to fetch whether it's starred
    const issueRef = {
      projectName: this.projectName,
      localId: this.issueId,
    };
    const starredIssues = issue.starredIssues(state);
    this._isStarred = starredIssues.has(issueRefToString(issueRef));
    this._fetchingIsStarred = issue.requests(state).fetchIsStarred.requesting;
    this._starringIssue = issue.requests(state).star.requesting;
  }

  updated(changedProperties) {
    if (changedProperties.has('projectName')
        || changedProperties.has('issueEntryUrl')) {
      this.bindProjectKeys(this.projectName, this.issueEntryUrl);
    }
    if (changedProperties.has('projectName') || changedProperties.has('issueId')
        || changedProperties.has('issuePermissions')
        || changedProperties.has('queryParams')) {
      this.bindIssueDetailKeys(this.projectName, this.issueId,
        this.issuePermissions, this.queryParams);
    }
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
      Mousetrap.bind('r', (e) => {
        e.preventDefault();

        // Force a hash change even the hash is already makechanges.
        if (window.location.hash.toLowerCase() === '#makechanges') {
          window.location.hash = ' ';
        }
        window.location.hash = '#makechanges';
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

          store.dispatch(issue.star(issueRef, newIsStarred));
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
}

customElements.define('mr-keystrokes', MrKeystrokes);
