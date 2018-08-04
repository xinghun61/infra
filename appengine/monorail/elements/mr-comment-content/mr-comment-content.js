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
	statePath: 'commentReferences',
      },
      // NOTE: This is not secure. It's just to temporarily remove extra HTML
      // that would show as plaintext.
      _contentWithoutHtml: {
        type: String,
        computed: '_stripHtml(content)',
      },
      _textRuns: {
        type: Array,
        value: () => ([]),
      },
    };
  }

  static get observers() {
    return [
      '_computeTextRuns(content, commentReferences)',
    ]
  }

  _computeCommentLines(comment) {
    return comment.trim().split(/(\r?\n)/);
  }

  _stripHtml(comment) {
    const temp = document.createElement('DIV');
    temp.innerHTML = comment;
    return temp.textContent || temp.innerText;
  }

  _isTagEqual(tag, str) {
    return tag == str;
  }

  _computeTextRuns(content, commentReferences) {
    this.set('_textRuns', []);
    if (content) {
      Polymer.RenderStatus.afterNextRender(this, function() {
        const autolinkedTextRuns = window.__autolink.markupAutolinks(content, commentReferences);
        this.set('_textRuns', autolinkedTextRuns);
      });
    }
  }
}
customElements.define(MrCommentContent.is, MrCommentContent);
