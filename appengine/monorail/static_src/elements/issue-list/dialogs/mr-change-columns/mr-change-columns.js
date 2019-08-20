// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import qs from 'qs';
import 'elements/chops/chops-button/chops-button.js';
import 'elements/chops/chops-dialog/chops-dialog.js';
import {SHARED_STYLES} from 'shared/shared-styles.js';
import {COLSPEC_DELIMITER_REGEX} from 'shared/issue-fields.js';

/**
 * `<mr-change-columns>`
 *
 * Dialog where the user can change columns on the list view.
 *
 */
export class MrChangeColumns extends LitElement {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        .edit-actions {
          margin: 0.5em 0;
          text-align: right;
        }
        .input-grid {
          align-items: center;
          width: 800px;
          max-width: 100%;
        }
        input {
          box-sizing: border-box;
          padding: 0.25em 4px;
        }
      `,
    ];
  }

  render() {
    return html`
      <chops-dialog closeOnOutsideClick>
        <h3 class="medium-heading">Change list columns</h3>
        <form id="changeColumns">
          <div class="input-grid">
            <label for="columnsInput">Columns: </label>
            <input
              id="columnsInput"
              placeholder="Edit columns..."
              value=${this.columnString}
            />
          </div>
          <div class="edit-actions">
            <chops-button
              @click=${this.close}
              class="de-emphasized discard-button"
            >
              Discard
            </chops-button>
            <chops-button
              @click=${this.save}
              class="emphasized"
            >
              Update columns
            </chops-button>
          </div>
        </form>
      </chops-dialog>
    `;
  }

  static get properties() {
    return {
      /**
       * Array of the currently configured issue columns, used to set
       * the default value.
       */
      columns: {type: Array},
      /**
       * Parsed query params for the current page, to be used in
       * navigation.
       */
      queryParams: {type: Object},
    };
  }

  constructor() {
    super();

    this.columns = [];
    this.queryParams = {};

    this._page = page;
  }

  get columnString() {
    return this.columns.join(' ');
  }

  /**
   * Abstract out the computation of the current page. Useful for testing.
   */
  get _currentPage() {
    return window.location.pathname;
  }

  save() {
    const input = this.shadowRoot.querySelector('#columnsInput');
    const newColumns = input.value.trim().split(COLSPEC_DELIMITER_REGEX);

    const params = {...this.queryParams};
    params.colspec = newColumns.join('+');

    // TODO(zhangtiff): Create a shared function to change only
    // query params in a URL.
    this._page(`${this._currentPage}?${qs.stringify(params)}`);

    this.close();
  }

  open() {
    this.reset();
    const dialog = this.shadowRoot.querySelector('chops-dialog');
    dialog.open();
  }

  close() {
    const dialog = this.shadowRoot.querySelector('chops-dialog');
    dialog.close();
  }

  reset() {
    this.shadowRoot.querySelector('form').reset();
  }
}

customElements.define('mr-change-columns', MrChangeColumns);
