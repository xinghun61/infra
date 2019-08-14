// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {issueRefToUrl, issueToIssueRef} from 'elements/shared/converters.js';
import '../../framework/mr-star-button/mr-star-button.js';

export class MrGridTile extends LitElement {
  render() {
    return html`
      <div class="tile-header">
        <mr-star-button
          .issueRef=${this.issueRef}
        ></mr-star-button>
        <a class="issue-id" href=${issueRefToUrl(this.issue, this.queryParams)}>
          ${this.issue.localId}
        </a>
        <div class="status">
          ${this.issue.statusRef ? this.issue.statusRef.status : ''}
        </div>
      </div>
      <div class="summary">
        ${this.issue.summary || ''}
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
      :host {
        display: block;
        border: 2px solid var(--chops-gray-200);
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
      :host(:hover) {
        border-color: var(--chops-blue-100);
      }
      .tile-header {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        margin-bottom: 0.1em;
      }
      mr-star-button {
        --mr-star-button-size: 16px;
      }
      a.issue-id {
        font-weight: 500;
        text-decoration: none;
        display: inline-block;
        padding-left: .25em;
        color: var(--chops-blue-700);
      }
      .status {
        display: inline-block;
        font-size: 90%;
        max-width: 30%;
        white-space: nowrap;
        padding-left: 4px;
      }
      .summary {
        height: 3.7em;
        font-size: 90%;
        line-height: 94%;
        padding: .05px .25em .05px .25em;
        position: relative;
      }
      a:hover {
        text-decoration: underline;
      }
    `;
  };
};

customElements.define('mr-grid-tile', MrGridTile);
