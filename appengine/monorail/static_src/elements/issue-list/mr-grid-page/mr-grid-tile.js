// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {issueRefToUrl, issueToIssueRef} from 'elements/shared/converters.js';
import '../../framework/mr-star-button/mr-star-button.js';

export class MrGridTile extends LitElement {
  render() {
    return html`
      <div class="tile">
      <div class="in-line-header">
        <mr-star-button
          .issueRef=${this.issueRef}
        ></mr-star-button>
        <a href=${this.issue.localId ?
            issueRefToUrl(this.issue, this.queryParams) : ''}>
            ${this.issue.localId ? html`
              <div class="ids">
                ${this.issue.localId}
              </div>` : html`<div class="ids"></div>
          `}
        </a>
          ${this.issue.statusRef ? html`
            <div class="status">
              ${this.issue.statusRef.status}
            </div>` : html`<div class="status"></div>
          `}
      </div>
        <div class="summary">
          ${this.issue.summary || ''}
        </div>
      </div>
    `;
  }

  static get properties() {
    return {
      issue: {type: Object},
      issueRef: {type: Object},
      queryParams: {type: Object},
    };
  };

  constructor() {
    super();
    this.issue = {};
    this.queryParams = '';
  };

  update(changedProperties) {
    if (changedProperties.has('issue')) {
      this.issueRef = issueToIssueRef(this.issue);
    }
    super.update(changedProperties);
  }

  static get styles() {
    return css`
      .tile {
        border: 2px solid #f1f1f1;
        border-radius: 6px;
        padding: 1px;
        margin: 3px;
        background: white;
        width: 10em;
        height: 5em;
        float: left;
        table-layout: fixed;
        overflow: hidden;
      }
      .in-line-header {
        display: flex;
      }
      a:link, a:visited {
        text-decoration: none;
        font-size: var(--chops-main-font-size);
        color: var(--chops-gray-800);
      }
      mr-star-button {
        float: left;
        display: inline-block;
        height: 1.5em;
      }
      .ids {
        font-size: var(--chops-large-font-size);
        font-weight: 500;
        display: inline-block;
        padding-left: .25em;
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
        padding: .05px .25em .05px .25em;
        position: relative;
      }
      a:hover {
        color: var(--chops-blue-700);
      }
    `;
  };
};

customElements.define('mr-grid-tile', MrGridTile);
