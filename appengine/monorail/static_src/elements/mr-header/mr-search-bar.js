// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import '../mr-dropdown/mr-dropdown.js';

/**
 * `<mr-search-bar>`
 *
 * The searchbar for Monorail.
 *
 */
export class MrSearchBar extends PolymerElement {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style>
        :host {
          --mr-search-bar-background: white;
          --mr-search-bar-border-radius: 4px;
          --mr-search-bar-border: var(--chops-accessible-border);
          --mr-search-bar-chip-color: var(--chops-gray-200);
          height: 26px;
          font-size: 14px;
        }
        input#searchq {
          display: flex;
          align-items: center;
          justify-content: flex-start;
          flex-grow: 2;
          min-width: 100px;
          border: none;
          border-top: var(--mr-search-bar-border);
          border-bottom: var(--mr-search-bar-border);
          background: var(--mr-search-bar-background);
          height: 100%;
          box-sizing: border-box;
          padding: 0 2px;
          font-size: inherit;
        }
        mr-dropdown {
          text-align: right;
          display: flex;
          text-overflow: ellipsis;
          box-sizing: border-box;
          background: var(--mr-search-bar-background);
          border: var(--mr-search-bar-border);
          border-left: 0;
          border-radius: 0 var(--mr-search-bar-border-radius)
            var(--mr-search-bar-border-radius) 0;
          height: 100%;
          align-items: center;
          justify-content: center;
          text-decoration: none;
        }
        button {
          font-size: inherit;
          order: -1;
          background: var(--mr-search-bar-background);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          box-sizing: border-box;
          border: var(--mr-search-bar-border);
          border-left: none;
          border-right: none;
          padding: 0 8px;
        }
        form {
          display: flex;
          height: 100%;
          width: 100%;
          align-items: center;
          justify-content: flex-start;
          flex-direction: row;
        }
        i.material-icons {
          font-size: 20px;
          color: var(--chops-primary-icon-color);
        }
        .select-container {
          order: -2;
          max-width: 150px;
          min-width: 50px;
          flex-shrink: 1;
          height: 100%;
          position: relative;
          box-sizing: border-box;
          border: var(--mr-search-bar-border);
          border-radius: var(--mr-search-bar-border-radius) 0 0
            var(--mr-search-bar-border-radius);
          background: var(--mr-search-bar-chip-color);
        }
        .select-container i.material-icons {
          display: flex;
          align-items: center;
          justify-content: center;
          position: absolute;
          right: 0;
          top: 0;
          height: 100%;
          width: 20px;
          z-index: 2;
          padding: 0;
        }
        select {
          display: flex;
          align-items: center;
          justify-content: flex-start;
          -webkit-appearance: none;
          -moz-appearance: none;
          appearance: none;
          text-overflow: ellipsis;
          cursor: pointer;
          width: 100%;
          height: 100%;
          background: none;
          margin: 0;
          padding: 0 20px 0 8px;
          box-sizing: border-box;
          border: 0;
          z-index: 3;
          font-size: inherit;
          position: relative;
        }
        select::-ms-expand {
          display: none;
        }
        select::after {
          position: relative;
          right: 0;
          content: 'arrow_drop_down';
          font-family: 'Material Icons';
        }
      </style>
      <form action\$="/p/[[projectName]]/issues/list" method="GET">
        <div class="select-container">
          <i class="material-icons">arrow_drop_down</i>
          <select name="can" on-change="_redirectOnSelect">
            <optgroup label="Search within">
              <option value="1">All issues</option>
              <option value="2">Open issues</option>
              <option value="3">Open and owned by me</option>
              <option value="4">Open and reported by me</option>
              <option value="5">Open and starred by me</option>
              <option value="8">Open with comment by me</option>
              <option value="6">New issues</option>
              <option value="7">Issues to verify</option>
            </optgroup>
            <optgroup label="Project queries" hidden$="[[!userDisplayName]]">
              <option data-href\$="/p/[[projectName]]/adminViews">Manage project queries...</option>
            </optgroup>
            <optgroup label="My saved queries" hidden$="[[!userDisplayName]]">
              <option data-href\$="/u/[[userDisplayName]]/queries">Manage my saved queries...</option>
            </optgroup>
          </select>
        </div>
        <input
          id="searchq"
          type="text"
          name="q"
          placeholder\$="Search [[projectName]] issues..."
          value\$="[[initialValue]]"
          autocomplete="off"
        />
        <button type="submit">
          <i class="material-icons">search</i>
        </button>
        <mr-dropdown
          items="[[_searchMenuItems]]"
        ></mr-dropdown>
      </form>
    `;
  }

  static get is() {
    return 'mr-search-bar';
  }

  static get properties() {
    // TODO(zhangtiff): Let's add
    return {
      projectName: String,
      userDisplayName: String,
      initialValue: String,
      _searchMenuItems: {
        type: Array,
        computed: '_computeSearchMenuItems(projectName)',
      },
    };
  }

  _computeSearchMenuItems(projectName) {
    return [
      {
        text: 'Advanced search',
        url: `/p/${projectName}/issues/advsearch`,
      },
      {
        text: 'Search tips',
        url: `/p/${projectName}/issues/searchtips`,
      },
    ];
  }

  _redirectOnSelect(evt) {
    const target = evt.target;
    const option = target.options[target.selectedIndex];

    if (option.dataset.href) {
      window.location.href = option.dataset.href;
    }
  }
}

customElements.define(MrSearchBar.is, MrSearchBar);
