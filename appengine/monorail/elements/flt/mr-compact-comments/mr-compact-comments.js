'use strict';

/**
 * `<mr-compact-comments>`
 *
 * Display Monorail comments in a dense and compact way. Currently used by the
 * feature launch tracking page.
 *
 */
class MrCompactComments extends Polymer.Element {
  static get is() {
    return 'mr-compact-comments';
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
      onSubmitComment: Function,
      user: {
        type: String,
        value: 'you@google.com',
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
      _newCommentText: String,
    };
  }

  toggleComments() {
    this._commentsHidden = !this._commentsHidden;
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

  _submitComment() {
    if (this.onSubmitComment) {
      this.onSubmitComment(this._newCommentText);
    }
    this.$.commentText.value = '';
  }

  _showDiff(comment) {
    return comment.descriptionNum || comment.amendments;
  }
}
customElements.define(MrCompactComments.is, MrCompactComments);
