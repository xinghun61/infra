// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-dialog/chops-dialog.js';
import {ReduxMixin} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';
import * as user from '../../redux/user.js';
import '../../shared/mr-shared-styles.js';

export class MrUpdateIssueHotlists extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-shared-styles">
        :host {
          font-size: var(--chops-main-font-size);
          --chops-dialog-theme: {
            max-width: 500px;
          };
        }
        select,
        input {
          @apply --mr-edit-field-styles;
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
        .error {
          max-width: 100%;
          color: red;
          margin-bottom: 1px;
        }
      </style>
      <chops-dialog>
        <h3 class="medium-heading">Add issue to hotlists</h3>
        <form id="issueHotlistsForm">
          <template is="dom-if" if="[[userHotlists.length]]">
            <template is="dom-repeat" items="[[userHotlists]]">
              <label title="[[item.name]]: [[item.summary]]">
                <input
                  title\$="[[_checkboxTitle(item, issueHotlists, this)]]"
                  on-click="_updateCheckboxTitle"
                  type="checkbox"
                  id\$="[[item.name]]"
                  checked\$="[[_issueInHotlist(item, issueHotlists)]]"
                >
                [[item.name]]
              </label>
            </template>
          </template>
          <h3 class="medium-heading">Create new hotlist</h3>
          <div class="input-grid">
            <label for="_newHotlistName">New hotlist name:</label>
            <input type="text" name="_newHotlistName" id="_newHotlistName">
          </div>
          <br>
          <template is="dom-if" if="[[error]]">
            <div class="error">[[error]]</div>
          </template>
          <div class="edit-actions">
            <chops-button on-click="discard" class="de-emphasized discard-button" disabled="[[disabled]]">
              Discard
            </chops-button>
            <chops-button on-click="save" class="emphasized" disabled="[[disabled]]">
              Save changes
            </chops-button>
          </div>
        </form>
      </chops-dialog>
    `;
  }

  static get is() {
    return 'mr-update-issue-hotlists';
  }

  static get properties() {
    return {
      issueRef: Object,
      issueHotlists: Array,
      userHotlists: Array,
      user: Object,
      error: String,
    };
  }

  static mapStateToProps(state, element) {
    return {
      issueRef: issue.issueRef(state),
      issueHotlists: issue.hotlists(state),
      user: user.user(state),
      userHotlists: user.user(state).hotlists,
    };
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

  save() {
    const changes = this.changes;
    const issueRef = this.issueRef;

    const promises = [];
    if (changes.added.length) {
      promises.push(window.prpcClient.call(
        'monorail.Features', 'AddIssuesToHotlists', {
          hotlistRefs: changes.added,
          issueRefs: [issueRef],
        }
      ));
    }
    if (changes.removed.length) {
      promises.push(window.prpcClient.call(
        'monorail.Features', 'RemoveIssuesFromHotlists', {
          hotlistRefs: changes.removed,
          issueRefs: [issueRef],
        }
      ));
    }
    if (changes.created) {
      promises.push(window.prpcClient.call(
        'monorail.Features', 'CreateHotlist', {
          name: changes.created.name,
          summary: changes.created.summary,
          issueRefs: [issueRef],
        }
      ));
    }

    Promise.all(promises).then((results) => {
      this.dispatchAction(issue.fetchHotlists(issueRef));
      this.dispatchAction(user.fetchHotlists(this.user.email));
      this.close();
    }, (error) => {
      this.error = error.description;
    });
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

  _checkboxTitle(hotlist, issueHotlists, foo) {
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
    if (form._newHotlistName.value) {
      changes.created = {
        name: form._newHotlistName.value,
        summary: 'Hotlist created from issue.',
      };
    }
    return changes;
  }
}

customElements.define(MrUpdateIssueHotlists.is, MrUpdateIssueHotlists);
