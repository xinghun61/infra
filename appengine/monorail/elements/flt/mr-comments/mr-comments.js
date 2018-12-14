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

  _deleteComment(comment) {
    const issueRef = {
      projectName: comment.projectName,
      localId: comment.localId,
    };
    window.prpcCall('monorail.Issues', 'DeleteIssueComment', {
      issueRef,
      sequenceNum: comment.sequenceNum,
      delete: comment.isDeleted === undefined,
    }).then((resp) => {
      actionCreator.fetchComments(this.dispatch.bind(this), {issueRef});
    });
  }

  _flagComment(comment) {
    const issueRef = {
      projectName: comment.projectName,
      localId: comment.localId,
    };
    window.prpcCall('monorail.Issues', 'FlagComment', {
      issueRef,
      sequenceNum: comment.sequenceNum,
      flag: comment.isSpam === undefined,
    }).then((resp) => {
      actionCreator.fetchComments(this.dispatch.bind(this), {issueRef});
    });
  }

  _offerCommentOptions(comment) {
    return comment.canDelete || comment.canFlag;
  }

  _canExpandDeletedComment(comment) {
    return ((comment.isSpam && comment.canFlag)
            || (comment.isDeleted && comment.canDelete));
  }

  _getCommentOptions(comment) {
    const options = [];
    if (comment.canDelete) {
      const text = (comment.isDeleted ? 'Undelete' : 'Delete') + ' comment';
      options.push({
        url: '#',
        text: text,
        handle: this._deleteComment.bind(this, comment),
        idx: options.length,
      });
    }
    if (comment.canFlag) {
      const text = (comment.isSpam ? 'Unflag' : 'Flag') + ' comment';
      options.push({
        url: '#',
        text: text,
        handle: this._flagComment.bind(this, comment),
        idx: options.length,
      });
    }
    return options;
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
    // If the comment is flagged/deleted and we have permission to
    // un-flag/un-delete it, then expand it if requested.
    if (!comment.isDeleted) {
      return false;
    }
    if (this._canExpandDeletedComment(comment)) {
      return deletedCommentsHidden;
    }
    // Otherwise, it should always be hidden.
    return true;
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
}
customElements.define(MrComments.is, MrComments);
