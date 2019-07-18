// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {issueRefToUrl} from 'elements/shared/converters.js';

export class MrGridTile extends LitElement {
  render() {
    return html`
      <a href=${this.issue.localId ?
          issueRefToUrl(this.issue, this.queryParams) : ''}>
        <div class="tile-header">
          ${this.issue.localId ? html`
            <div class="ids">
              ${this.issue.localId}
            </div>` : html`<div class="ids"></div>
          `}
          ${this.issue.statusRef ? html`
            <div class="status">
              ${this.issue.statusRef.status}
            </div>` : html`<div class="status"></div>
          `}
        </div>
        ${this.issue.summary ? html`
          <div class="summary">
            ${this.issue.summary}
          </div>` : html`<div class="summary"></div>
        `}
      </a>
    `;
  }

  static get properties() {
    return {
      issue: {type: Object},
      queryParams: {type: Object},
    };
  };

  constructor() {
    super();
    this.issue = {};
    this.queryParams = '';
  };

  static get styles() {
    return css`
      a:link, a:visited{
        text-decoration: none;
        font-size: var(--chops-main-font-size);
        color: var(--chops-gray-800);
        border: 2px solid #f1f1f1;
        border-radius: 6px;
        padding: 1px;
        margin: 3px;
        background: white;
        width: 10em;
        float: left;
        table-layout: fixed;
        overflow: hidden;
      }
      .tile-header {
        display: flex;
        height: 1.5em;
      }
      .ids {
        font-size: var(--chops-large-font-size);
        font-weight: 500;
        display: inline-block;
        padding-left: 2.5em;
      }
      .status {
        display: inline-block;
        font-size: 90%;
        padding-left: .5em;
      }
      .summary {
        height: 3.7em;
        font-size: 90%;
        line-height: 94%;
        padding: 0px .25em .05px .25em;
      }
      a:hover {
        color: var(--chops-blue-700);
      }
    `;
  };
};

customElements.define('mr-grid-tile', MrGridTile);
