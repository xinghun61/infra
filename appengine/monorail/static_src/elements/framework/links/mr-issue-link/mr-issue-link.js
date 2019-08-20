// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {ifDefined} from 'lit-html/directives/if-defined';
import {issueRefToString, issueRefToUrl} from 'shared/converters.js';

/**
 * `<mr-issue-link>`
 *
 * Displays a link to an issue.
 *
 */
export class MrIssueLink extends LitElement {
  static get styles() {
    return css`
      a[is-closed] {
        text-decoration: line-through;
      }
    `;
  }

  render() {
    return html`
      <a
        id="bugLink"
        href=${issueRefToUrl(this.issue, this.queryParams)}
        title=${ifDefined(this.issue && this.issue.summary)}
        ?is-closed=${this.isClosed}
      >${this._linkText}</a>
    `;
  }

  static get properties() {
    return {
      // The issue being viewed. Falls back gracefully if this is only a ref.
      issue: {type: Object},
      text: {type: String},
      // The global current project name. NOT the issue's project name.
      projectName: {type: String},
      queryParams: {type: Object},
      short: {type: Boolean},
    };
  }

  constructor() {
    super();

    this.issue = {};
    this.queryParams = {};
    this.short = false;
  }

  click() {
    const link = this.shadowRoot.querySelector('a');
    if (!link) return;
    link.click();
  }

  get isClosed() {
    if (!this.issue || !this.issue.statusRef) return false;

    return this.issue.statusRef.meansOpen === false;
  }

  get _linkText() {
    const {projectName, issue, text, short} = this;
    if (text) return text;

    if (issue && issue.extIdentifier) {
      return issue.extIdentifier;
    }

    const prefix = short ? '' : 'Issue ';

    return prefix + issueRefToString(issue, projectName);
  }
}

customElements.define('mr-issue-link', MrIssueLink);
