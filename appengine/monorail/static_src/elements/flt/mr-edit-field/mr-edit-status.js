// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {flush} from '@polymer/polymer/lib/utils/flush.js';

import {issueStringToRef} from '../../shared/converters.js';
import '../../shared/mr-shared-styles.js';
import './mr-edit-field.js';


/**
 * `<mr-edit-metadata>`
 *
 * Editing form for either an approval or the overall issue.
 *
 */
export class MrEditStatus extends PolymerElement {
  static get template() {
    return html`
      <style include="mr-shared-styles">
        :host {
          width: 100%;
        }
        select {
          @apply --mr-edit-field-styles;
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
      </style>
      <select id="statusInput" on-change="_statusInputChanged" aria-label="Status">
        <template is="dom-repeat" items="[[_statusesGrouped]]" as="group">
          <optgroup label$="[[group.name]]" hidden$="[[!group.name]]">
            <template is="dom-repeat" items="[[group.statuses]]">
              <option
                value$="[[item.status]]"
                selected$="[[_computeIsSelected(status, item.status)]]"
              >
                [[item.status]]
                <template is="dom-if" if="[[item.docstring]]">
                  = [[item.docstring]]
                </template>
              </option>
            </template>
          </optgroup>

          <template is="dom-if" if="[[!group.name]]">
            <template is="dom-repeat" items="[[group.statuses]]">
              <option
                value$="[[item.status]]"
                selected$="[[_computeIsSelected(status, item.status)]]"
              >
                [[item.status]]
                <template is="dom-if" if="[[item.docstring]]">
                  = [[item.docstring]]
                </template>
              </option>
            </template>
          </template>
        </template>
      </select>

      <div class="grid-input" hidden$="[[!_showMergedInto]]">
        <label for="mergedIntoInput" id="mergedIntoLabel">Merged into:</label>
        <mr-edit-field
          id="mergedIntoInput"
          initial-values="[[mergedInto]]"
          on-change="_onChange"
        ></mr-edit-field>
      </div>`;
  }

  static get is() {
    return 'mr-edit-status';
  }

  static get properties() {
    return {
      status: {
        type: String,
        value: '',
        observer: '_initialStatusChanged',
      },
      statuses: {
        type: Array,
        value: () => [],
      },
      isApproval: {
        type: Boolean,
        value: false,
      },
      mergedInto: {
        type: String,
        value: '',
      },
      _statusesGrouped: {
        type: Array,
        computed: '_computeStatusesGrouped(statuses, isApproval)',
      },
      _showMergedInto: Boolean,
    };
  }

  reset() {
    const mergedIntoInput = this.shadowRoot.querySelector('#mergedIntoInput');
    if (mergedIntoInput) {
      mergedIntoInput.reset();
    }
    const initialIndex = this.statuses.findIndex(
      (option) => this.status === option.status);
    this.shadowRoot.querySelector('#statusInput').selectedIndex = initialIndex;
    this._initialStatusChanged();
    flush();
  }

  getDelta(projectName) {
    const result = {};
    const root = this.shadowRoot;

    const statusInput = root.querySelector('#statusInput');
    if (statusInput) {
      const newStatus = statusInput.value;
      if (newStatus !== this.status) {
        result['status'] = newStatus;
      }
    }

    if (this.status === 'Duplicate' && !this._showMergedInto) {
      result['mergedIntoRef'] = {};
    } else if (this._showMergedInto) {
      const newMergedInto = root.querySelector(
        '#mergedIntoInput').getValue();
      if (newMergedInto !== this.mergedInto[0]) {
        result['mergedIntoRef'] = issueStringToRef(projectName, newMergedInto);
      }
    }

    return result;
  }

  _computeIsSelected(a, b) {
    return a === b;
  }

  _computeStatusesGrouped(statuses, isApproval) {
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

  _statusInputChanged() {
    const statusInput = this.shadowRoot.querySelector('#statusInput');
    this._showMergedInto = (statusInput.value === 'Duplicate');
    this._onChange();
  }

  _initialStatusChanged() {
    this._showMergedInto = (this.status === 'Duplicate');
  }

  _onChange() {
    this.dispatchEvent(new CustomEvent('change'));
  }
}

customElements.define(MrEditStatus.is, MrEditStatus);
