// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import './mr-grid-dropdown';
import './mr-button-group';

const DEFAULT_ISSUE_PROPERTIES =
  ['None', 'Attachments', 'Blocked', 'BlockedOn',
    'Blocking', 'Component', 'Reporter', 'Stars', 'Status', 'Type'];


export class MrGridControls extends LitElement {
  render() {
    return html`
    <div class="flex-container">
      <div>
      <div class="rowscols">
        <mr-grid-dropdown
          class="rows"
          .text=${'Rows'}
          .items=${this.issueProperties}>
        </mr-grid-dropdown>
        <mr-grid-dropdown
          class="cols"
          .text=${'Cols'}
          .items=${this.issueProperties}>
        </mr-grid-dropdown>
      </div>
      <div class="cell-selector">
        <mr-button-group .options = ${this.cells}>
        </mr-button-group>
      </div>
      </div>
      <div class="view-selector">
        <mr-button-group .options=${this.viewSelector}>
        </mr-button-group>
      </div>
    </div>
      `;
  }

  constructor() {
    super();
    this.issueProperties = DEFAULT_ISSUE_PROPERTIES;
    this.cells = ['Tiles', 'Ids', 'Counts'];
    this.viewSelector = ['List', 'Grid', 'Chart'];
  };

  static get properties() {
    return {
      issueProperties: {type: Array},
      cells: {type: Array},
    };
  };

  static get styles() {
    return css`
      .flex-container {
        display: flex;
        justify-content: space-between;
        margin-top: 20px;
        aign-items: center;
        margin-right: 20px;
      }
      .rows {
        display: inline-block;
        padding-left: 20px;
      }
      .cols {
        display: inline-block;
        padding-left: 20px;
      }
      .rowscols {
        display: inline-block;
      }
      .cell-selector {
        padding-left: 20px;
        display: inline-block;
      }
    `;
  };
};

customElements.define('mr-grid-controls', MrGridControls);
