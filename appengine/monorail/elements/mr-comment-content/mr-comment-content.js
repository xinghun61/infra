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
      _textRuns: {
        type: Array,
        value: () => ([]),
      },
    };
  }

  static get observers() {
    return [
      '_computeTextRuns(content)',
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

  _computeTextRuns(content) {
    // TODO(jojwang): monorail:4033, add autolinking for issues, users, links, etc.
    const chunks = content.trim().split(/(<b>[^<\n]+<\/b>)|(\r?\n)/);
    let textRuns = [];
    chunks.forEach(chunk => {
      if (chunk) {
        let textRun = {};
        if (chunk.match(/\r/) || chunk.match(/\n/)) {
          textRun.tag = 'br';
        } else if (chunk.startsWith('<b>') && chunk.endsWith('</b>')) {
          textRun.content = chunk.slice(3,-4);
          textRun.tag = 'b';
        } else {
          textRun.content = chunk;
        }
        textRuns.push(textRun);
      }
    });
    this.set('_textRuns', textRuns);
  }
}
customElements.define(MrCommentContent.is, MrCommentContent);
