// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {ReduxMixin} from '../../redux/redux-mixin.js';
import * as user from '../../redux/user.js';
import '../shared/mr-flt-styles.js';

export class MrUpdateIssueHotlists extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-flt-styles">
        :host {
          padding: 1em;
          display: block;
          font-size: 12px;
          --mr-edit-field-styles: {
            box-sizing: border-box;
            width: 95%;
            padding: 0.25em 4px;
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
        label {
          font-weight: bold;
          word-wrap: break-word;
          text-align: right;
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
        .discard-button {
          margin-right: 16px;
        }
        .edit-actions {
          width: 100%;
          margin: 0.5em 0;
          text-align: right;
        }
        .input-grid {
          padding: 0.5em 0;
          display: grid;
          max-width: 100%;
          grid-gap: 10px;
          grid-template-columns: 120px auto;
          align-items: flex-start;
        }
        .error {
          max-width: 100%;
          color: red;
          margin-bottom: 1px;
        }
      </style>
      <h3 class="medium-heading">Add issue to hotlists</h3>
      <form id="issueHotlistsForm">
        <template is="dom-if" if="[[userHotlists.length]]">
          <div class="input-grid">
            <template is="dom-repeat" items="[[userHotlists]]">
              <input
                title\$="[[_checkboxTitle(item, issueHotlists, this)]]"
                on-click="_updateCheckboxTitle"
                type="checkbox"
                id\$="[[item.name]]"
                checked\$="[[_issueInHotlist(item, issueHotlists)]]"
              >
              <span style="display: contents" title="[[item.name]]: [[item.summary]]">[[item.name]]</span>
              <br>
            </template>
          </div>
          <br>
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
            <i class="material-icons">close</i>
            Discard changes
          </chops-button>
          <chops-button on-click="save" class="emphasized" disabled="[[disabled]]">
            <i class="material-icons">create</i>
            Save changes
          </chops-button>
        </div>
      </form>
    `;
  }

  static get is() {
    return 'mr-update-issue-hotlists';
  }

  static get properties() {
    return {
      issueHotlists: Array,
      userHotlists: Array,
      error: String,
    };
  }

  static mapStateToProps(state, element) {
    return {
      issueHotlists: state.issueHotlists,
      userHotlists: user.currentUser(state).hotlists,
    };
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
    this.userHotlists.forEach((hotlist) => {
      const issueInHotlist = this._issueInHotlist(hotlist, this.issueHotlists);
      const hotlistIsChecked = this.$.issueHotlistsForm[hotlist.name].checked;
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
    if (this.$.issueHotlistsForm._newHotlistName.value) {
      changes.created = {
        name: this.$.issueHotlistsForm._newHotlistName.value,
        summary: 'Hotlist created from issue.',
      };
    }
    return changes;
  }

  reset() {
    this.$.issueHotlistsForm.reset();
    this.error = '';
  }

  discard() {
    this.dispatchEvent(new CustomEvent('discard'));
  }

  save() {
    this.dispatchEvent(new CustomEvent('save'));
  }
}

customElements.define(MrUpdateIssueHotlists.is, MrUpdateIssueHotlists);
