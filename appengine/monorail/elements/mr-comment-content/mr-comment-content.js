// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '../../node_modules/@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';
import {autolink} from '../../static/js/autolink.js';
import {ReduxMixin} from '../redux/redux-mixin.js';

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
          word-wrap: break-word;
          word-break: break-all;
        }
        .line {
          white-space: pre-wrap;
        }
        .strike-through {
          text-decoration: line-through;
        }
        .deleted-comment-content {
          color: #888;
          font-style: italic;
        }
      </style>
      <span class\$="[[_computeDeletedClass(isDeleted)]]">
        <template is="dom-repeat" items="[[_textRuns]]" as="run">
          <b class="line" hidden\$="[[!_isTagEqual(run.tag, 'b')]]">[[run.content]]</b>
          <br hidden\$="[[!_isTagEqual(run.tag, 'br')]]">
          <a class="line" hidden\$="[[!_isTagEqual(run.tag, 'a')]]" target="_blank" href\$="[[run.href]]" class\$="[[run.css]]">[[run.content]]</a>
          <span class="line" hidden\$="[[run.tag]]">[[run.content]]</span>
        </template>
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
      projectName: String,
      _textRuns: {
        type: Array,
        computed: '_computeTextRuns(isDeleted, content, commentReferences, projectName)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      commentReferences: state.commentReferences,
      projectName: state.projectName,
    };
  }

  _isTagEqual(tag, str) {
    return tag == str;
  }

  _computeTextRuns(isDeleted, content, commentReferences, projectName) {
    return autolink.markupAutolinks(
      content, commentReferences, projectName);
  }

  _computeDeletedClass(isDeleted) {
    return isDeleted ? 'deleted-comment-content' : '';
  }
}
customElements.define(MrCommentContent.is, MrCommentContent);
