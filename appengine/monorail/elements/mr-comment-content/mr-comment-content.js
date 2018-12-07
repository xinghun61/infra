'use strict';

/**
 * `<mr-comment-content>`
 *
 * Displays text for a comment.
 *
 */
class MrCommentContent extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-comment-content';
  }

  static get properties() {
    return {
      content: String,
      commentReferences: {
        type: Object,
        value: () => new Map(),
        statePath: 'commentReferences',
      },
      isDeleted: Boolean,
      projectName: {
        type: String,
        statePath: 'projectName',
      },
      _textRuns: {
        type: Array,
        computed: '_computeTextRuns(isDeleted, content, commentReferences, projectName)',
      },
    };
  }

  _isTagEqual(tag, str) {
    return tag == str;
  }

  _computeTextRuns(isDeleted, content, commentReferences, projectName) {
    console.log(isDeleted);
    return window.__autolink.markupAutolinks(
        content, commentReferences, projectName);
  }

  _computeDeletedClass(isDeleted) {
    console.log(isDeleted ? 'deleted-comment-content' : '');
    return isDeleted ? 'deleted-comment-content' : '';
  }
}
customElements.define(MrCommentContent.is, MrCommentContent);
