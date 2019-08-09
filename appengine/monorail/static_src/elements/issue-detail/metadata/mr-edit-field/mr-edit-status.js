// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {SHARED_STYLES} from 'elements/shared/shared-styles';
import './mr-edit-field.js';

/**
 * `<mr-edit-status>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
export class MrEditStatus extends LitElement {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          width: 100%;
        }
        select {
          width: var(--mr-edit-field-width);
          padding: var(--mr-edit-field-padding);
        }
        .grid-input {
          margin-top: 8px;
          display: grid;
          grid-gap: var(--mr-input-grid-gap);
          grid-template-columns: auto 1fr;
        }
        .grid-input[hidden] {
          display: none;
        }
        label {
          font-weight: bold;
          word-wrap: break-word;
          text-align: left;
        }
      `,
    ];
  }

  render() {
    return html`
      <select
        @change=${this._selectChangeHandler}
        aria-label="Status"
        id="statusInput"
      >
        ${this._statusesGrouped.map((group) => html`
          <optgroup label=${group.name} ?hidden=${!group.name}>
            ${group.statuses.map((item) => html`
              <option
                value=${item.status}
                .selected=${this.status === item.status}
              >
                ${item.status}
                ${item.docstring ? `= ${item.docstring}` : ''}
              </option>
            `)}
          </optgroup>

          ${!group.name ? html`
            ${group.statuses.map((item) => html`
              <option
                value=${item.status}
                .selected=${this.status === item.status}
              >
                ${item.status}
                ${item.docstring ? `= ${item.docstring}` : ''}
              </option>
            `)}
          ` : ''}
        `)}
      </select>

      <div class="grid-input" ?hidden=${!this._showMergedInto}>
        <label for="mergedIntoInput" id="mergedIntoLabel">Merged into:</label>
        <mr-edit-field
          id="mergedIntoInput"
          .initialValues=${this.mergedInto ? [this.mergedInto] : []}
          @change=${this._changeHandler}
        ></mr-edit-field>
      </div>`;
  }

  static get properties() {
    return {
      initialStatus: {type: String},
      status: {type: String},
      statuses: {type: Array},
      isApproval: {type: Boolean},
      mergedInto: {type: String},
    };
  }

  update(changedProperties) {
    if (changedProperties.has('initialStatus')) {
      this.status = this.initialStatus;
    }
    super.update(changedProperties);
  }

  get _showMergedInto() {
    const status = this.status || this.initialStatus;
    return (status === 'Duplicate');
  }

  get _statusesGrouped() {
    const statuses = this.statuses;
    const isApproval = this.isApproval;
    if (!statuses) return [];
    if (isApproval) {
      return [{statuses: statuses}];
    }
    return [
      {
        name: 'Open',
        statuses: statuses.filter((s) => s.meansOpen),
      },
      {
        name: 'Closed',
        statuses: statuses.filter((s) => !s.meansOpen),
      },
    ];
  }

  async reset() {
    await this.updateComplete;
    const mergedIntoInput = this.shadowRoot.querySelector('#mergedIntoInput');
    if (mergedIntoInput) {
      mergedIntoInput.reset();
    }
    this.status = this.initialStatus;
  }

  get delta() {
    const result = {};

    if (this.status !== this.initialStatus) {
      result['status'] = this.status;
    }

    if (this._showMergedInto) {
      const newMergedInto = this.shadowRoot.querySelector(
          '#mergedIntoInput').value;
      if (newMergedInto !== this.mergedInto) {
        result['mergedInto'] = newMergedInto;
      }
    } else if (this.initialStatus === 'Duplicate') {
      result['mergedInto'] = '';
    }

    return result;
  }

  _selectChangeHandler(e) {
    const statusInput = e.target;
    this.status = statusInput.value;
    this._changeHandler(e);
  }

  _changeHandler(e) {
    this.dispatchEvent(new CustomEvent('change'));
  }
}

customElements.define('mr-edit-status', MrEditStatus);
