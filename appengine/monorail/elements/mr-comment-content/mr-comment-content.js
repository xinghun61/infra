'use strict';

/**
 * `<mr-comment-content>`
 *
 * Displays text for a comment.
 *
 */
class MrCommentContent extends Polymer.Element {
  static get is() {
    return 'mr-comment-content';
  }

  static get properties() {
    return {
      content: String,
      // NOTE: This is not secure. It's just to temporarily remove extra HTML
      // that would show as plaintext.
      _contentWithoutHtml: {
        type: String,
        computed: '_stripHtml(content)',
      },
    };
  }

  _computeCommentLines(comment) {
    return comment.trim().split(/(\r?\n)/);
  }

  _stripHtml(comment) {
    const temp = document.createElement('DIV');
    temp.innerHTML = comment;
    return temp.textContent || temp.innerText;
  }
}
customElements.define(MrCommentContent.is, MrCommentContent);
