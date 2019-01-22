'use strict';

/**
 * `<mr-inline-editor>`
 *
 * A component for editing bodies of text such as issue descriptions or the
 * survey.
 *
 */
class MrInlineEditor extends Polymer.Element {
  static get is() {
    return 'mr-inline-editor';
  }

  static get properties() {
    return {
      content: {
        type: String,
        observer: '_processRawContent',
      },
      _displayedContent: {
        type: String,
        value: '',
      },
      editing: {
        type: Boolean,
        value: false,
      },
      editText: {
        type: String,
        value: 'Edit',
      },
      headingLevel: {
        type: Number,
        value: 3,
      },
      placeholder: String,
      _boldLines: {
        type: Array,
        value: () => [],
      },
      sendEmail: {
        type: Boolean,
        value: true,
      },
      title: {
        type: String,
        value: 'Editable content',
      },
    };
  }

  _processRawContent(content) {
    const chunks = content.trim().split(/(<b>[^<\n]+<\/b>)/m);
    let boldLines = [];
    let cleanContent = '';
    chunks.forEach((chunk) => {
      if (chunk.startsWith('<b>') && chunk.endsWith('</b>')) {
        const cleanChunk = chunk.slice(3, -4).trim();
        cleanContent += cleanChunk;
        // Don't add whitespace to boldLines.
        if (/\S/.test(cleanChunk)) {
          boldLines.push(cleanChunk);
        }
      } else {
        cleanContent += chunk;
      }
    });
    this.set('_boldLines', boldLines);
    this._displayedContent = cleanContent;
  }

  edit() {
    this.editing = true;
    this.$.textEditor.focus();
  }

  cancel() {
    this.editing = false;
  }

  save() {
    const newContentMarked = this._markupNewContent();

    this.dispatchEvent(new CustomEvent('save', {detail: {
      commentContent: newContentMarked,
      sendEmail: this.sendEmail,
    }}));
    this.cancel();
  }

  _markupNewContent() {
    const lines = this._displayedContent.trim().split('\n');
    const markedLines = lines.map((line) => {
      let markedLine = line;
      const matchingBoldLine = this._boldLines.find(
        (boldLine) => (line.startsWith(boldLine)));
      if (matchingBoldLine) {
        markedLine =
          `<b>${matchingBoldLine}</b>${line.slice(matchingBoldLine.length)}`;
      }
      return markedLine;
    });
    return markedLines.join('\n');
  }

  _sendEmailChecked(evt) {
    this.sendEmail = evt.detail.checked;
  }
}
customElements.define(MrInlineEditor.is, MrInlineEditor);
