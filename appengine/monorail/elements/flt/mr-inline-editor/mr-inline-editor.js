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
        notify: true,
      },
      editing: {
        type: Boolean,
        value: false,
      },
      editText: {
        type: String,
        value: 'Edit',
      },
      placeholder: String,
      title: {
        type: String,
        value: 'Editable content',
      },
      _newContent: String,
    };
  }

  edit() {
    this.editing = true;
    this.$.textEditor.focus();
  }

  cancel() {
    this.editing = false;
  }

  save() {
    this.cancel();
    this.content = this._newContent;
  }
}
customElements.define(MrInlineEditor.is, MrInlineEditor);
