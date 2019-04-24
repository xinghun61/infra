// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {autolink} from 'autolink.js';
import {connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';

/**
 * `<mr-comment-content>`
 *
 * Displays text for a comment.
 *
 */
export class MrCommentContent extends connectStore(PolymerElement) {
  static get template() {
    return html`
      <style>
        :host {
          word-break: break-word;
          font-size: var(--chops-main-font-size);
          line-height: 130%;
          font-family: var(--mr-toggled-font-family);
        }
        :host[is-deleted] {
          color: #888;
          font-style: italic;
        }
        .line {
          white-space: pre-wrap;
        }
        .strike-through {
          text-decoration: line-through;
        }
      </style>
      <template is="dom-repeat" items="[[_textRuns]]" as="run"
        ><b
            class="line"
            hidden\$="[[!_isTagEqual(run.tag, 'b')]]"
          >[[run.content]]</b
        ><br hidden\$="[[!_isTagEqual(run.tag, 'br')]]"
        ><a
            class="line"
            hidden\$="[[!_isTagEqual(run.tag, 'a')]]"
            target="_blank"
            href\$="[[run.href]]"
            class\$="[[run.css]]"
            title\$="[[run.title]]"
          >[[run.content]]</a
        ><span class="line" hidden\$="[[run.tag]]">[[run.content]]</span
      ></template>
    `;
  }

  static get is() {
    return 'mr-comment-content';
  }

  static get properties() {
    return {
      content: String,
      commentReferences: {
        type: Object,
        value: () => new Map(),
      },
      isDeleted: {
        type: Boolean,
        reflectToAttribute: true,
      },
      projectName: String,
      _textRuns: {
        type: Array,
        computed: '_computeTextRuns(content, commentReferences, projectName)',
      },
    };
  }

  stateChanged(state) {
    this.setProperties({
      commentReferences: issue.commentReferences(state),
      projectName: issue.issueRef(state).projectName,
    });
  }

  _isTagEqual(tag, str) {
    return tag == str;
  }

  _computeTextRuns(content, commentReferences, projectName) {
    return autolink.markupAutolinks(
      content, commentReferences, projectName);
  }
}
customElements.define(MrCommentContent.is, MrCommentContent);
