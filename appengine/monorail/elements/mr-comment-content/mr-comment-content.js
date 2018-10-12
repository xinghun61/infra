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
      _textRuns: {
        type: Array,
        computed: '_computeTextRuns(content, commentReferences)',
      },
    };
  }

  _isTagEqual(tag, str) {
    return tag == str;
  }

  _computeTextRuns(content, commentReferences) {
    return window.__autolink.markupAutolinks(content, commentReferences);
  }
}
customElements.define(MrCommentContent.is, MrCommentContent);
