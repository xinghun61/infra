// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {ifDefined} from 'lit-html/directives/if-defined';
import {autolink} from 'autolink.js';
import {connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';

/**
 * `<mr-comment-content>`
 *
 * Displays text for a comment.
 *
 */
export class MrCommentContent extends connectStore(LitElement) {
  constructor() {
    super();

    this.content = '';
    this.commentReferences = new Map();
    this.isDeleted = false;
    this.projectName = '';
  }

  static get properties() {
    return {
      content: {type: String},
      commentReferences: {type: Object},
      isDeleted: {
        type: Boolean,
        reflect: true,
      },
      projectName: {type: String},
    };
  }

  static get styles() {
    return css`
      :host {
        word-break: break-word;
        font-size: var(--chops-main-font-size);
        line-height: 130%;
        font-family: var(--mr-toggled-font-family);
      }
      :host([isDeleted]) {
        color: #888;
        font-style: italic;
      }
      .line {
        white-space: pre-wrap;
      }
      .strike-through {
        text-decoration: line-through;
      }
    `;
  }

  render() {
    const runs = autolink.markupAutolinks(
      this.content, this.commentReferences, this.projectName);
    const templates = runs.map((run) => {
      switch (run.tag) {
        case 'b':
          return html`<b class="line">${run.content}</b>`;
        case 'br':
          return html`<br>`;
        case 'a':
          return html`<a
            class="line"
            target="_blank"
            href=${run.href}
            class=${run.css}
            title=${ifDefined(run.title)}
          >${run.content}</a>`;
        default:
          return html`<span class="line">${run.content}</span>`;
      }
    });
    return html`${templates}`;
  }

  stateChanged(state) {
    this.commentReferences = issue.commentReferences(state);
    this.projectName = issue.issueRef(state).projectName;
  }
}
customElements.define('mr-comment-content', MrCommentContent);
