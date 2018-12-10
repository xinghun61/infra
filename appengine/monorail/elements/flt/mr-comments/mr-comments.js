'use strict';

/**
 * `<mr-comments>`
 *
 * Display Monorail comments in a dense and compact way. Currently used by the
 * feature launch tracking page.
 *
 */
class MrComments extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-comments';
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
      user: {
        type: String,
        statePath: 'user',
      },
      _commentsHidden: {
        type: Boolean,
        value: true,
      },
      _commentsHiddenCount: {
        type: Number,
        computed: '_computeCommentsHiddenCount(commentsShownCount, comments.length)',
      },
      _deletedCommentsHidden: {
        type: Boolean,
        value: true,
      },
      _hideToggle: {
        type: Boolean,
        value: false,
        computed: '_computeHideToggle(_commentsHiddenCount)',
      },
      _hideDeletedToggle: {
        type: Boolean,
        value: false,
        computed: '_computeHideDeletedToggle(comments)',
      },
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

  toggleDeletedComments() {
    this._deletedCommentsHidden = !this._deletedCommentsHidden;
  }

  _hideDeletedComment(deletedCommentsHidden, comment) {
    return comment.isDeleted && (deletedCommentsHidden || !comment.canDelete);
  }

  _computeDeleteCommentVerb(comment) {
    return comment.isDeleted ? 'Undelete' : 'Delete';
  }

  _computeHideDeletedToggle(comments) {
    return !comments.some((comment) => {
      return comment.isDeleted && comment.canDelete;
    });
  }

  _pluralize(count, baseWord, pluralWord) {
    pluralWord = pluralWord || `${baseWord}s`;
    return count == 1 ? baseWord : pluralWord;
  }

  _showDiff(comment) {
    return comment.descriptionNum || comment.amendments;
  }

  _deleteComment(e) {
    const issueRef = {
      projectName: e.target.dataset.projectName,
      localId: e.target.dataset.localId,
    };
    window.prpcCall('monorail.Issues', 'DeleteIssueComment', {
      issueRef,
      sequenceNum: e.target.dataset.sequenceNum,
      delete: e.target.dataset.isDeleted === undefined,
    }).then((resp) => {
      actionCreator.fetchComments(this.dispatch.bind(this), {issueRef});
    });
  }
}
customElements.define(MrComments.is, MrComments);
