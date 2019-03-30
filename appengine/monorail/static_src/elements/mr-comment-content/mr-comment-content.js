// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {autolink} from '../../autolink.js';
import {ReduxMixin} from '../redux/redux-mixin.js';
import * as issue from '../redux/issue.js';
import * as user from '../redux/user.js';

/**
 * `<mr-comment-content>`
 *
 * Displays text for a comment.
 *
 */
export class MrCommentContent extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style>
        :host {
          word-break: break-word;
          font-size: var(--chops-main-font-size);
          line-height: 130%;
        }
        .line {
          white-space: pre-wrap;
        }
        .strike-through {
          text-decoration: line-through;
        }
        span[is-deleted] {
          color: #888;
          font-style: italic;
        }
        span[code-font] {
          font-family: monospace;
        }
      </style>
      <span is-deleted\$="[[isDeleted]]" code-font\$="[[_codeFont]]">
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
      </span>
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
      isDeleted: Boolean,
      prefs: Object,
      projectName: String,
      _textRuns: {
        type: Array,
        computed: '_computeTextRuns(isDeleted, content, commentReferences, projectName)',
      },
      _codeFont: {
        type: Boolean,
        computed: '_computeCodeFont(prefs)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      commentReferences: state.commentReferences,
      projectName: issue.issueRef(state).projectName,
      prefs: user.user(state).prefs,
    };
  }

  _isTagEqual(tag, str) {
    return tag == str;
  }

  _computeTextRuns(isDeleted, content, commentReferences, projectName) {
    return autolink.markupAutolinks(
      content, commentReferences, projectName);
  }

  _computeCodeFont(prefs) {
    if (!prefs) return false;
    return prefs.get('code_font') === 'true';
  }
}
customElements.define(MrCommentContent.is, MrCommentContent);
