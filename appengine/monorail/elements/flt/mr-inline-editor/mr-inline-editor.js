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
      content: String,
      _displayedContent: String,
      editing: {
        type: Boolean,
        value: false,
      },
      editText: {
        type: String,
        value: 'Edit',
      },
      placeholder: String,
      _boldLines: {
        type: Array,
        value: () => [],
      },
      title: {
        type: String,
        value: 'Editable content',
      },
      onSave: Function,
      _newContent: String,
    };
  }

  static get observers() {
    return [
      '_processRawContent(content)',
    ]
  }

  _processRawContent(content) {
    const chunks = content.trim().split(/(<b>[^<\n]+<\/b>)/m);
    let boldLines = [];
    let cleanContent = '';
    chunks.forEach(chunk => {
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
    if (this.onSave) {
      const newContentMarked = this._markupNewContent();
      this.onSave(newContentMarked);
    }
    this.cancel();
  }

  _markupNewContent() {
    const lines = this._displayedContent.trim().split('\n');
    let markedContent = '';
    let markedLines = [];
    lines.forEach(line => {
      let markedLine = line;
      this._boldLines.forEach(boldLine => {
        if (line.startsWith(boldLine)) {
          markedLine = `<b>${boldLine}</b>${line.slice(boldLine.length)}`;
        }
      });
      markedLines.push(markedLine);
    });
    return markedLines.join('\n');
  }

}
customElements.define(MrInlineEditor.is, MrInlineEditor);
