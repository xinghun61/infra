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
      _hideToggle: {
        type: Boolean,
        value: false,
        computed: '_computeHideToggle(_commentsHiddenCount)',
      },
      _expandedDeletedComments: {
        type: Object,
        value: {},
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

  _toggleHideDeletedComment(comment, shouldExpand) {
    const expandComment = Object.assign({}, this._expandDeletedComments);
    expandComment[comment.sequenceNum] = shouldExpand;
    this._expandedDeletedComments = expandComment;
  }

  _offerCommentOptions(comment) {
    return comment.canDelete || comment.canFlag;
  }

  _canExpandDeletedComment(comment) {
    return ((comment.isSpam && comment.canFlag)
            || (comment.isDeleted && comment.canDelete));
  }

  _hideDeletedComment(expandedDeletedComments, comment) {
    return (comment.isDeleted
            && !expandedDeletedComments[comment.sequenceNum]);
  }

  _getCommentOptions(expandedDeletedComments, comment) {
    const options = [];
    if (this._canExpandDeletedComment(comment)) {
      const expanded = expandedDeletedComments[comment.sequenceNum];
      const text = (expanded ? 'Hide' : 'Show') + ' comment content';
      options.push({
        url: '#',
        text: text,
        handle: this._toggleHideDeletedComment.bind(this, comment, !expanded),
        idx: options.length,
      });
      options.push({separator: true});
    }
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

  _pluralize(count, baseWord, pluralWord) {
    pluralWord = pluralWord || `${baseWord}s`;
    return count == 1 ? baseWord : pluralWord;
  }

  _showDiff(comment) {
    return comment.descriptionNum || comment.amendments;
  }
}
customElements.define(MrComments.is, MrComments);
