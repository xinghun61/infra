// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-button/chops-button.js';
import './mr-comment.js';
import {ReduxMixin, actionCreator} from '../../redux/redux-mixin.js';
import '../shared/mr-flt-styles.js';

const ISSUE_EDIT_PERMISSION = 'editissue';

/**
 * `<mr-comment-list>`
 *
 * Display a list of Monorail comments.
 *
 */
export class MrCommentList extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <style include="mr-flt-styles">
        button.toggle {
          background: none;
          color: var(--chops-link-color);
          border: 0;
          border-bottom: var(--chops-normal-border);
          width: 100%;
          padding: 0.5em 8px;
          text-align: left;
          font-size: 110%;
        }
        button.toggle:hover {
          cursor: pointer;
          text-decoration: underline;
        }
        button.toggle[hidden] {
          display: none;
        }
      </style>
      <button on-click="toggleComments" class="toggle" hidden\$="[[_hideToggle]]">
        [[_computeCommentToggleVerb(_commentsHidden)]]
        [[_commentsHiddenCount]]
        older
        [[_pluralize(_commentsHiddenCount, 'comment')]]
      </button>
      <template is="dom-repeat" items="[[comments]]" as="comment">
        <mr-comment
          focus-id="[[focusId]]"
          comment="[[comment]]"
          hidden\$="[[_computeCommentHidden(_commentsHidden, _commentsHiddenCount, index)]]"
          heading-level="[[headingLevel]]"
          quick-mode="[[quickMode]]"
        ></mr-comment>
      </template>
      <template is="dom-if" if="[[_shouldOfferEdit(issuePermissions)]]">
        <slot></slot>
      </template>
    `;
  }

  static get is() {
    return 'mr-comment-list';
  }

  static get properties() {
    return {
      commentsShownCount: {
        type: Number,
        value: 2,
      },
      comments: {
        type: Array,
        value: [],
      },
      headingLevel: {
        type: Number,
        value: 4,
      },
      issuePermissions: Object,
      focusId: String,
      quickMode: {
        type: Boolean,
        value: false,
      },
      _commentsHidden: {
        type: Boolean,
        value: true,
      },
      _commentsHiddenCount: {
        type: Number,
        computed: '_computeCommentsHiddenCount(commentsShownCount, comments.length)',
      },
      _hideToggle: {
        type: Boolean,
        value: false,
        computed: '_computeHideToggle(_commentsHiddenCount)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      focusId: state.focusId,
      issuePermissions: state.issuePermissions,
    };
  }

  ready() {
    super.ready();
    this.addEventListener('expand-parent', () => {
      this.showComments();
    });
  }

  toggleComments() {
    this._commentsHidden = !this._commentsHidden;
  }

  showComments(evt) {
    this._commentsHidden = false;

    if (evt && evt.detail && evt.detail.callback) {
      evt.detail.callback();
    }
  }

  _shouldOfferEdit(issuePermissions) {
    return (issuePermissions || []).includes(ISSUE_EDIT_PERMISSION);
  }

  _computeCommentHidden(commentsHidden, commentsHiddenCount, index) {
    return commentsHidden && index < commentsHiddenCount;
  }

  _computeCommentsHiddenCount(shownCount, numComments) {
    return Math.max(numComments - shownCount, 0);
  }

  _computeHideToggle(hiddenCount) {
    return hiddenCount <= 0;
  }

  _computeCommentToggleVerb(commentsHidden) {
    return commentsHidden ? 'Show' : 'Hide';
  }

  _pluralize(count, baseWord, pluralWord) {
    pluralWord = pluralWord || `${baseWord}s`;
    return count == 1 ? baseWord : pluralWord;
  }
}
customElements.define(MrCommentList.is, MrCommentList);
