// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import qs from 'qs';
import {connectStore} from 'reducers/base.js';
import * as issue from 'reducers/issue.js';
import * as project from 'reducers/project.js';
import 'elements/chops/chops-choice-buttons/chops-choice-buttons.js';
import '../mr-mode-selector/mr-mode-selector.js';
import './mr-grid-dropdown.js';
import {getAvailableGridFields} from './extract-grid-data.js';

export class MrGridControls extends connectStore(LitElement) {
  static get styles() {
    return css`
      :host {
        display: flex;
        justify-content: space-between;
        margin-top: 20px;
        box-sizing: border-box;
        padding: 0 20px;
      }
      .rows, .cols {
        padding-right: 20px;
      }
      .left-controls {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        flex-grow: 0;
      }
      .right-controls {
        display: flex;
        align-items: center;
        flex-grow: 0;
      }
      .issue-count {
        display: inline-block;
        padding-right: 20px;
      }
    `;
  };

  render() {
    const hideCounts = this.totalIssues === 0;
    return html`
      <div class="left-controls">
        <mr-grid-dropdown
          class="rows"
          .text=${'Rows'}
          .items=${this.gridOptions}
          .selection=${this.queryParams.y}
          @change=${this._rowChanged}>
        </mr-grid-dropdown>
        <mr-grid-dropdown
          class="cols"
          .text=${'Cols'}
          .items=${this.gridOptions}
          .selection=${this.queryParams.x}
          @change=${this._colChanged}>
        </mr-grid-dropdown>
        <chops-choice-buttons
          class="cell-selector"
          .options=${this.cells}
          @change=${this._selectCell}
          .value=${this.cellType}>
        </chops-choice-buttons>
      </div>
      <div class="right-controls">
        ${hideCounts ? '' : html`
          <div class="issue-count">
            ${this.issueCount}
            of
            ${this.totalIssues}
            ${this.totalIssues === 1 ? html`
              issue `: html`
              issues `} shown
          </div>
        `}
        <mr-mode-selector
          .projectName=${this.projectName}
          .queryParams=${this.queryParams}
          value="grid"
        ></mr-mode-selector>
      </div>
    `;
  }

  constructor() {
    super();
    this.gridOptions = getAvailableGridFields();
    this.cells = [
      {text: 'Tile', value: 'tiles'},
      {text: 'IDs', value: 'ids'},
      {text: 'Counts', value: 'counts'},
    ];
    this.modeOptions = [
      {text: 'List', value: 'list'},
      {text: 'Grid', value: 'grid'},
      {text: 'Chart', value: 'chart'},
    ];
    this.queryParams = {y: 'None', x: 'None'};
    this.cellType = 'tiles';

    this.totalIssues = 0;
    this._fieldDefs = [];
    this._labelPrefixFields = [];
  };

  static get properties() {
    return {
      gridOptions: {type: Array},
      cells: {type: Array},
      cellType: {type: String},
      modeOptions: {type: Array},
      projectName: {tupe: String},
      queryParams: {type: Object},
      issueCount: {type: Number},
      totalIssues: {type: Number},
      _fieldDefs: {type: Array},
      _labelPrefixFields: {type: Object},
    };
  };

  stateChanged(state) {
    this.totalIssues = (issue.totalIssues(state) || 0);
    this._fieldDefs = project.fieldDefs(state) || [];
    this._labelPrefixFields = project.labelPrefixFields(state) || [];
  }

  update(changedProperties) {
    if (changedProperties.has('_fieldDefs')
        || changedProperties.has('_labelPrefixFields')) {
      this.gridOptions = getAvailableGridFields(
          this._fieldDefs, this._labelPrefixFields);
    }
    if (changedProperties.has('cells') && this.queryParams.cells) {
      this.cellType = this.queryParams.cells;
    }
    super.update(changedProperties);
  }

  _rowChanged(e) {
    this.queryParams.y = e.target.selection;
    const params = Object.assign({}, this.queryParams);
    if (this.queryParams.y === 'None') {
      params.y = '';
    }
    this._changeUrlParams(params);
  }

  _colChanged(e) {
    this.queryParams.x = e.target.selection;
    const params = Object.assign({}, this.queryParams);
    if (this.queryParams.x === 'None') {
      params.x = '';
    }
    this._changeUrlParams(params);
  }

  _changeUrlParams(params) {
    const newParams = qs.stringify(params);
    const newUrl = `${location.pathname}?${newParams}`;
    page(newUrl);
  }

  _selectCell(e) {
    this.queryParams.cells = e.target.value;
    this._changeUrlParams(this.queryParams);
  }
};

customElements.define('mr-grid-controls', MrGridControls);
