// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import './mr-grid-dropdown';
import './mr-choice-buttons';
import page from 'page';
import qs from 'qs';

const DEFAULT_ISSUE_PROPERTIES =
  ['None', 'Attachments', 'Blocked', 'BlockedOn',
    'Blocking', 'Component', 'Reporter', 'Stars', 'Status', 'Type'];

export class MrGridControls extends LitElement {
  render() {
    return html`
    <div>
    <div class="rowscols">
      <mr-grid-dropdown
        class="rows"
        .text=${'Rows'}
        .items=${this.issueProperties}
        .selection=${this.queryParams.y}
        @change=${this._rowChanged}>
      </mr-grid-dropdown>
      <mr-grid-dropdown
        class="cols"
        .text=${'Cols'}
        .items=${this.issueProperties}
        .selection=${this.queryParams.x}
        @change=${this._colChanged}>
      </mr-grid-dropdown>
    </div>
    <div class="cell-selector">
      <mr-choice-buttons
        class='cells'
        .options=${this.cells}
        @change=${this._cellSelected}
        .value=${this.cellType}>
      </mr-choice-buttons>
    </div>
    </div>
    <div class="view-selector">
      <mr-choice-buttons
        .options=${this.viewSelector}
        @change=${this._viewSelected}
        .value=${'grid'}>
      </mr-choice-buttons>
    </div>
      `;
  }

  constructor() {
    super();
    this.issueProperties = DEFAULT_ISSUE_PROPERTIES;
    this.cells = [
      {text: 'Tile', value: 'tiles'},
      {text: 'IDs', value: 'ids'},
      {text: 'Counts', value: 'counts'},
    ];
    this.viewSelector = [
      {text: 'List', value: 'list'},
      {text: 'Grid', value: 'grid'},
      {text: 'Chart', value: 'chart'},
    ];
    this.queryParams = {y: 'None', x: 'None'};
    this.cellType = 'tiles';
  };

  static get properties() {
    return {
      issueProperties: {type: Array},
      cells: {type: Array},
      cellType: {type: String},
      viewSelector: {type: Array},
      queryParams: {type: Object},
      customIssueProperties: {type: Array},
    };
  };

  update(changedProperties) {
    if (changedProperties.has('customIssueProperties')) {
      const customFields = this.customIssueProperties.map((property) =>
        property.fieldRef.fieldName);
      // TODO(zosha): sort custom properties alphabetically.
      this.issueProperties = DEFAULT_ISSUE_PROPERTIES.concat(customFields);
    }
    if (changedProperties.has('cells') && this.queryParams.cells) {
      this.cellType = this.queryParams.cells;
    }
    super.update(changedProperties);
  }

  static get styles() {
    return css`
      :host {
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

  _rowChanged(e) {
    this.queryParams.y = e.target.selection;
    this._changeUrlParams(this.queryParams);
  }

  _colChanged(e) {
    this.queryParams.x = e.target.selection;
    this._changeUrlParams(this.queryParams);
  }

  _changeUrlParams(params) {
    const newParams = qs.stringify(params);
    const newUrl = `${location.pathname}?${newParams}`;
    page(newUrl);
  }

  _cellSelected(e) {
    this.queryParams.cells = e.target.value;
    this._changeUrlParams(this.queryParams);
  }

  _viewSelected(e) {
    const value = e.target.value.toLowerCase();
    if (value !== 'grid') {
      if (value === 'chart') {
        this.queryParams.mode = 'chart';
      } else {
        delete this.queryParams.mode;
      }
      const params = qs.stringify(this.queryParams);
      const newURL =
        `${location.pathname.replace('list_new', 'list')}?${params}`;
      page(newURL);
    }
  }
};

customElements.define('mr-grid-controls', MrGridControls);
