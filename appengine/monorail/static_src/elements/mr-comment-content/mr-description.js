// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {PolymerElement, html} from '@polymer/polymer';
import './mr-comment-content.js';

import {standardTimeShort} from
  '../chops/chops-timestamp/chops-timestamp-helpers';


/**
 * `<mr-description>`
 *
 * Element for displaying a description or survey.
 *
 */
export class MrDescription extends PolymerElement {
  static get template() {
    return html`
      <style>
        .select-container {
          width: 100%;
          float: left;
        }
        select {
          float: right;
        }
      </style>
      <div class="select-container">
        <select on-change="_selectChanged" hidden\$="[[!_hasDescriptionSelector]]">
          <template is="dom-repeat" items="[[descriptionList]]" as="description">
            <option value$="[[index]]" selected$="[[_isSelected(index, selectedIndex)]]">
              Description #[[_addOne(index)]] by [[description.commenter.displayName]]
              ([[_formatRelativeTime(description.timestamp)]])
            </option>
          </template>
        </select>
      </div>
      <mr-comment-content
        content="[[_selectedDescription.content]]"
      ></mr-comment-content>
    `;
  }

  static get is() {
    return 'mr-description';
  }

  static get properties() {
    return {
      descriptionList: {
        type: Array,
        observer: '_onDescriptionListChanged',
      },
      selectedIndex: Number,
      _selectedDescription: {
        type: Text,
        computed: '_computeSelectedDescription(descriptionList, selectedIndex)',
      },
      _hasDescriptionSelector: {
        type: Boolean,
        computed: '_computeHasDescriptionSelector(descriptionList)',
      },
    };
  }

  _computeHasDescriptionSelector(descriptionList) {
    return descriptionList && descriptionList.length > 1;
  }

  _computeSelectedDescription(descriptionList, selectedIndex) {
    if (!descriptionList || !descriptionList.length
      || selectedIndex === undefined || selectedIndex < 0
      || selectedIndex >= descriptionList.length) return {};
    return descriptionList[selectedIndex];
  }

  _onDescriptionListChanged(descriptionList) {
    if (!descriptionList || !descriptionList.length) return;
    this.selectedIndex = descriptionList.length - 1;
  }

  _isSelected(index, selectedIndex) {
    return index === selectedIndex;
  }

  _selectChanged(evt) {
    if (!evt || !evt.target) return;
    this.selectedIndex = Number.parseInt(evt.target.value);
  }

  _formatRelativeTime(unixTime) {
    unixTime = Number.parseInt(unixTime);
    if (Number.isNaN(unixTime)) return;
    return standardTimeShort(new Date(unixTime * 1000));
  }

  _addOne(num) {
    return num + 1;
  }
}
customElements.define(MrDescription.is, MrDescription);
