// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import './mr-comment-content.js';
import './mr-attachment.js';

import {standardTimeShort} from
  'elements/chops/chops-timestamp/chops-timestamp-helpers';


/**
 * `<mr-description>`
 *
 * Element for displaying a description or survey.
 *
 */
export class MrDescription extends LitElement {
  constructor() {
    super();

    this.descriptionList = [];
    this.selectedIndex = 0;
  }

  static get properties() {
    return {
      descriptionList: {type: Array},
      selectedIndex: {type: Number},
    };
  }

  updated(changedProperties) {
    super.updated(changedProperties);

    if (changedProperties.has('descriptionList')) {
      if (!this.descriptionList || !this.descriptionList.length) return;
      this.selectedIndex = this.descriptionList.length - 1;
    }
  }

  static get styles() {
    return css`
      .select-container {
        text-align: right;
      }
    `;
  }

  render() {
    const selectedDescription =
      (this.descriptionList || [])[this.selectedIndex] || {};

    return html`
      <div class="select-container">
        <select
          @change=${this._selectChanged}
          ?hidden=${!this.descriptionList || this.descriptionList.length <= 1}
          aria-label="Description history menu">
          ${this.descriptionList.map((description, index) => html`
            <option value=${index} ?selected=${index === this.selectedIndex}>
              Description #${index + 1} by ${description.commenter.displayName}
              (${_relativeTime(description.timestamp)})
            </option>
          `)}
        </select>
      </div>
      <mr-comment-content
        .content=${selectedDescription.content}
      ></mr-comment-content>
      <div>
        ${(selectedDescription.attachments || []).map((attachment) => html`
          <mr-attachment
            .attachment=${attachment}
            .projectName=${selectedDescription.projectName}
            .localId=${selectedDescription.localId}
            .sequenceNum=${selectedDescription.sequenceNum}
            .canDelete=${selectedDescription.canDelete}
          ></mr-attachment>
        `)}
      </div>
    `;
  }

  _selectChanged(evt) {
    if (!evt || !evt.target) return;
    this.selectedIndex = Number.parseInt(evt.target.value);
  }
}

function _relativeTime(unixTime) {
  unixTime = Number.parseInt(unixTime);
  if (Number.isNaN(unixTime)) return;
  return standardTimeShort(new Date(unixTime * 1000));
}

customElements.define('mr-description', MrDescription);
