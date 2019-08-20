// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import 'elements/chops/chops-dialog/chops-dialog.js';
import {store, connectStore} from 'reducers/base.js';
import * as issue from 'reducers/issue.js';
import * as user from 'reducers/user.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import {prpcClient} from 'prpc-client-instance.js';

export class MrUpdateIssueHotlists extends connectStore(LitElement) {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          font-size: var(--chops-main-font-size);
          --chops-dialog-max-width: 500px;
        }
        select,
        input {
          box-sizing: border-box;
          width: var(--mr-edit-field-width);
          padding: var(--mr-edit-field-padding);
          font-size: var(--chops-main-font-size);
        }
        input[type="checkbox"] {
          width: auto;
          height: auto;
        }
        button.toggle {
          background: none;
          color: hsl(240, 100%, 40%);
          border: 0;
          width: 100%;
          padding: 0.25em 0;
          text-align: left;
        }
        button.toggle:hover {
          cursor: pointer;
          text-decoration: underline;
        }
        label {
          display: flex;
          line-height: 200%;
          align-items: center;
          width: 100%;
          text-align: left;
          font-weight: normal;
          padding: 0.25em 8px;
          box-sizing: border-box;
        }
        label input[type="checkbox"] {
          margin-right: 8px;
        }
        .discard-button {
          margin-right: 16px;
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: right;
        }
        .input-grid {
          align-items: center;
        }
        .input-grid > input {
          width: 200px;
          max-width: 100%;
        }
        .error {
          max-width: 100%;
          color: red;
          margin-bottom: 1px;
        }
      `,
    ];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <chops-dialog closeOnOutsideClick>
        <h3 class="medium-heading">Add issue to hotlists</h3>
        <form id="issueHotlistsForm">
          ${this.userHotlists.length ? this.userHotlists.map((hotlist) => html`
            <label title="${hotlist.name}: ${hotlist.summary}">
              <input
                title=${this._checkboxTitle(hotlist, this.issueHotlists)}
                type="checkbox"
                id=${hotlist.name}
                ?checked=${this._issueInHotlist(hotlist, this.issueHotlists)}
                @click=${this._updateCheckboxTitle}
              >
              ${hotlist.name}
            </label>
          `) : ''}
          <h3 class="medium-heading">Create new hotlist</h3>
          <div class="input-grid">
            <label for="newHotlistName">New hotlist name:</label>
            <input type="text" name="newHotlistName">
          </div>
          <br>
          ${this.error ? html`
            <div class="error">${this.error}</div>
          `: ''}
          <div class="edit-actions">
            <chops-button
              class="de-emphasized discard-button"
              ?disabled=${this.disabled}
              @click=${this.discard}
            >
              Discard
            </chops-button>
            <chops-button
              class="emphasized"
              ?disabled=${this.disabled}
              @click=${this.save}
            >
              Save changes
            </chops-button>
          </div>
        </form>
      </chops-dialog>
    `;
  }

  static get properties() {
    return {
      viewedIssueRef: {type: Object},
      issueRefs: {type: Array},
      issueHotlists: {type: Array},
      userHotlists: {type: Array},
      user: {type: Object},
      error: {type: String},
    };
  }

  stateChanged(state) {
    this.viewedIssueRef = issue.issueRef(state);
    this.user = user.user(state);
    this.userHotlists = user.user(state).hotlists;
  }

  constructor() {
    super();

    this.issueRefs = [];
    this.issueHotlists = [];
    this.userHotlists = [];
  }

  open() {
    this.reset();
    this.shadowRoot.querySelector('chops-dialog').open();
  }

  reset() {
    this.shadowRoot.querySelector('#issueHotlistsForm').reset();
    this.error = '';
  }

  discard() {
    this.close();
  }

  close() {
    this.shadowRoot.querySelector('chops-dialog').close();
  }

  async save() {
    const changes = this.changes;
    const issueRefs = this.issueRefs;
    const viewedRef = this.viewedIssueRef;

    if (!issueRefs || !changes) return;

    const promises = [];
    if (changes.added && changes.added.length) {
      promises.push(prpcClient.call(
          'monorail.Features', 'AddIssuesToHotlists', {
            hotlistRefs: changes.added,
            issueRefs,
          }
      ));
    }
    if (changes.removed && changes.removed.length) {
      promises.push(prpcClient.call(
          'monorail.Features', 'RemoveIssuesFromHotlists', {
            hotlistRefs: changes.removed,
            issueRefs,
          }
      ));
    }
    if (changes.created) {
      promises.push(prpcClient.call(
          'monorail.Features', 'CreateHotlist', {
            name: changes.created.name,
            summary: changes.created.summary,
            issueRefs,
          }
      ));
    }

    try {
      await Promise.all(promises);

      // Refresh the viewed issue's hotlists only if there is a viewed issue.
      if (viewedRef) {
        const viewedIssueWasUpdated = issueRefs.find((ref) =>
          ref.projectName === viewedRef.projectName
          && ref.localId === viewedRef.localId);
        if (viewedIssueWasUpdated) {
          store.dispatch(issue.fetchHotlists(viewedRef));
        }
      }
      store.dispatch(user.fetchHotlists(this.user.email));
      this.close();
    } catch (error) {
      this.error = error.description;
    }
  }

  _issueInHotlist(hotlist, issueHotlists) {
    return issueHotlists.some((issueHotlist) => {
      return (hotlist.ownerRef.userId === issueHotlist.ownerRef.userId
        && hotlist.name === issueHotlist.name);
    });
  }

  _getCheckboxTitle(isChecked) {
    return (isChecked ? 'Remove issue from' : 'Add issue to') + ' this hotlist';
  }

  _checkboxTitle(hotlist, issueHotlists) {
    return this._getCheckboxTitle(this._issueInHotlist(hotlist, issueHotlists));
  }

  _updateCheckboxTitle(e) {
    e.target.title = this._getCheckboxTitle(e.target.checked);
  }

  get changes() {
    const changes = {
      added: [],
      removed: [],
    };
    const form = this.shadowRoot.querySelector('#issueHotlistsForm');
    this.userHotlists.forEach((hotlist) => {
      const issueInHotlist = this._issueInHotlist(hotlist, this.issueHotlists);
      const hotlistIsChecked = form[hotlist.name].checked;
      if (issueInHotlist && !hotlistIsChecked) {
        changes.removed.push({
          name: hotlist.name,
          owner: hotlist.ownerRef,
        });
      } else if (!issueInHotlist && hotlistIsChecked) {
        changes.added.push({
          name: hotlist.name,
          owner: hotlist.ownerRef,
        });
      }
    });
    if (form.newHotlistName.value) {
      changes.created = {
        name: form.newHotlistName.value,
        summary: 'Hotlist created from issue.',
      };
    }
    return changes;
  }
}

customElements.define('mr-update-issue-hotlists', MrUpdateIssueHotlists);
