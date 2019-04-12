// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {issueRefToString} from '../../shared/converters.js';

/**
 * `<mr-issue-link>`
 *
 * Displays a link to an issue.
 *
 */
export class MrIssueLink extends PolymerElement {
  static get template() {
    return html`
      <style>
        :host([is-closed]) a {
          text-decoration: line-through;
        }
      </style>
      <a
        id="bugLink"
        href$="[[_issueUrl]]"
        title$="[[issue.summary]]"
      >[[_linkText]]</a>
    `;
  }

  static get is() {
    return 'mr-issue-link';
  }

  static get properties() {
    return {
      // The issue being viewed. Falls back gracefully if this is only a ref.
      issue: Object,
      text: String,
      isClosed: {
        type: Boolean,
        reflectToAttribute: true,
        computed: '_computeIsClosed(issue.statusRef.meansOpen)',
      },
      // The global current project name. NOT the issue's project name.
      projectName: String,
      _issueUrl: {
        type: String,
        computed: '_computeIssueUrl(issue)',
      },
      _linkText: {
        type: String,
        computed: '_computeLinkText(projectName, issue, text)',
      },
    };
  }

  _computeIsClosed(isOpen) {
    // Undefined could mean that no status has been found for the issue yet.
    return isOpen === false;
  }

  _computeIssueUrl(issue) {
    return `/p/${issue.projectName}/issues/detail?id=${issue.localId}`;
  }

  _computeLinkText(projectName, issue, text) {
    if (text) return text;
    return `Issue ${issueRefToString(issue, projectName)}`;
  }
}
customElements.define(MrIssueLink.is, MrIssueLink);
