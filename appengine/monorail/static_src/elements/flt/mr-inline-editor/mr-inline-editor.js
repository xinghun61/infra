// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../chops/chops-button/chops-button.js';
import '../../chops/chops-checkbox/chops-checkbox.js';
import '../shared/mr-flt-styles.js';

/**
 * `<mr-inline-editor>`
 *
 * A component for editing bodies of text such as issue descriptions or the
 * survey.
 *
 */
export class MrInlineEditor extends PolymerElement {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-flt-styles">
        :host {
          display: block;
          width: 100%;
          color: hsl(0, 0%, 30%);
          box-sizing: border-box;
          word-wrap: break-word;
          --mr-inline-editor-textarea-min-height: 200px;
          --mr-inline-editor-textarea-max-height: 500px;
        }
        [role="heading"] {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          @apply --mr-inline-editor-header-style;
        }
        .content {
          padding: 0.5em 0;
          width: 100%;
          box-sizing: border-box;
        }
        .edit-controls {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        textarea.content {
          min-height: var(--mr-inline-editor-textarea-min-height);
          max-height: var(--mr-inline-editor-textarea-max-height);
          border: var(--chops-accessible-border);
          padding: 0.5em 4px;
        }
      </style>
      <div class="medium-heading" role="heading" aria-level\$="[[headingLevel]]">
        [[title]]

        <template is="dom-if" if="[[!editing]]">
          <chops-button on-click="edit">
            <i class="material-icons">create</i>
            [[editText]]
          </chops-button>
        </template>
      </div>
      <textarea id="textEditor" class="content" value="{{_displayedContent::input}}" hidden\$="[[!editing]]" placeholder\$="[[placeholder]]"></textarea>
      <template is="dom-if" if="[[editing]]">
        <div class="edit-controls">
          <chops-checkbox id="sendEmail" on-checked-change="_sendEmailChecked" checked="[[sendEmail]]">Send email</chops-checkbox>
          <div>
            <chops-button id="discard" on-click="cancel" class="de-emphasized">
              <i class="material-icons">close</i>
              Discard changes
            </chops-button>
            <chops-button id="save" on-click="save" class="emphasized">
              <i class="material-icons">create</i>
              Save changes
            </chops-button>
          </div>
        </div>
      </template>
      <div class="content" hidden\$="[[editing]]">
        <slot></slot>
      </div>
    `;
  }

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

  /**
   * Public API for setting content in this component,
   * currently mostly used for tests.
   **/
  setContent(content) {
    this._displayedContent = content;
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
