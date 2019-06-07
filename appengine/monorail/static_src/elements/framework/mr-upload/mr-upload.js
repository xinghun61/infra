// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import {SHARED_STYLES} from 'elements/shared/shared-styles.js';

/**
 * `<mr-upload>`
 *
 * A file uploading widget for use in adding attachments and similar things.
 *
 */
export class MrUpload extends LitElement {
  static get styles() {
    return [
      SHARED_STYLES,
      css`
        :host {
          display: block;
          width: 100%;
          padding: 0.25em 4px;
          border: 1px dashed var(--chops-gray-300);
          box-sizing: border-box;
          border-radius: 8px;
          transition: background 0.2s ease-in-out,
            border-color 0.2s ease-in-out;
        }
        :host([hidden]) {
          display: none;
        }
        :host([expanded]) {
          /* Expand the drag and drop area when a file is being dragged. */
          min-height: 120px;
        }
        :host([highlighted]) {
          border-color: var(--chops-primary-accent-color);
          background: var(--chops-primary-accent-bg);
        }
        input[type="file"] {
          /* We need the file uploader to be hidden but still accessible. */
          opacity: 0;
          width: 0;
          height: 0;
          position: absolute;
          top: -9999;
          left: -9999;
        }
        input[type="file"]:focus + label {
          /* TODO(zhangtiff): Find a way to either mimic native browser focus
           * styles or make focus styles more consistent. */
          box-shadow: 0 0 3px 1px hsl(193, 82%, 63%);
        }
        label.button {
          margin-right: 8px;
          padding: 0.1em 4px;
          display: inline-flex;
          width: auto;
          cursor: pointer;
          border: var(--chops-normal-border);
          margin-left: 0;
        }
        label.button i.material-icons {
          font-size: var(--chops-icon-font-size);
        }
        ul {
          display: flex;
          align-items: flex-start;
          justify-content: flex-start;
          flex-direction: column;
        }
        ul[hidden] {
          display: none;
        }
        li {
          display: inline-flex;
          align-items: center;
        }
        li i.material-icons {
          font-size: 14px;
          margin: 0;
        }
        /* TODO(zhangtiff): Create a shared Material icon button component. */
        button {
          border-radius: 50%;
          cursor: pointer;
          background: 0;
          border: 0;
          padding: 0.25em;
          margin-left: 4px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          transition: background 0.2s ease-in-out;
        }
        button:hover {
          background: var(--chops-gray-200);
        }
        .controls {
          display: flex;
          flex-direction: row;
          align-items: center;
          justify-content: flex-start;
          width: 100%;
        }
      `,
    ];
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons"
            rel="stylesheet">
      <div class="controls">
        <input id="file-uploader" type="file" multiple @change=${this._filesChanged}>
        <label class="button" for="file-uploader">
          <i class="material-icons" role="presentation">attach_file</i>Add attachments
        </label>
        Drop files here to add them (Max: 10.0 MB per comment)
      </div>
      <ul ?hidden=${!this.files || !this.files.length}>
        ${this.files.map((file, i) => html`
          <li>
            ${file.name}
            <button data-index=${i} @click=${this._removeFile}>
              <i class="material-icons">clear</i>
            </button>
          </li>
        `)}
      </ul>
    `;
  }

  static get properties() {
    return {
      files: {type: Array},
      highlighted: {
        type: Boolean,
        reflect: true,
      },
      expanded: {
        type: Boolean,
        reflect: true,
      },
      _boundOnDragIntoWindow: {type: Object},
      _boundOnDragOutOfWindow: {type: Object},
      _boundOnDragInto: {type: Object},
      _boundOnDragLeave: {type: Object},
      _boundOnDrop: {type: Object},
    };
  }

  constructor() {
    super();

    this.expanded = false;
    this.highlighted = false;
    this.files = [];
    this._boundOnDragIntoWindow = this._onDragIntoWindow.bind(this);
    this._boundOnDragOutOfWindow = this._onDragOutOfWindow.bind(this);
    this._boundOnDragInto = this._onDragInto.bind(this);
    this._boundOnDragLeave = this._onDragLeave.bind(this);
    this._boundOnDrop = this._onDrop.bind(this);
  }

  connectedCallback() {
    super.connectedCallback();
    this.addEventListener('dragenter', this._boundOnDragInto);
    this.addEventListener('dragover', this._boundOnDragInto);

    this.addEventListener('dragleave', this._boundOnDragLeave);
    this.addEventListener('drop', this._boundOnDrop);

    window.addEventListener('dragenter', this._boundOnDragIntoWindow);
    window.addEventListener('dragover', this._boundOnDragIntoWindow);
    window.addEventListener('dragleave', this._boundOnDragOutOfWindow);
    window.addEventListener('drop', this._boundOnDragOutOfWindow);
  }

  disconnectedCallback() {
    super.disconnectedCallback();

    window.removeEventListener('dragenter', this._boundOnDragIntoWindow);
    window.removeEventListener('dragover', this._boundOnDragIntoWindow);
    window.removeEventListener('dragleave', this._boundOnDragOutOfWindow);
    window.removeEventListener('drop', this._boundOnDragOutOfWindow);
  }

  reset() {
    this.files = [];
  }

  async loadFiles() {
    // TODO(zhangtiff): Add preloading of files on change.
    if (!this.files || !this.files.length) return [];
    const loads = this.files.map(this._loadLocalFile);
    return await Promise.all(loads);
  }

  _onDragInto(e) {
    // Combined event handler for dragenter and dragover.
    if (!this._eventGetFiles(e).length) return;
    e.preventDefault();
    this.highlighted = true;
  }

  _onDragLeave(e) {
    // Unhighlight the drop area when the user undrops the component.
    if (!this._eventGetFiles(e).length) return;
    e.preventDefault();
    this.highlighted = false;
  }

  _onDrop(e) {
    // Add the files the user is dragging when dragging into the component.
    const files = this._eventGetFiles(e);
    if (!files.length) return;
    e.preventDefault();
    this.highlighted = false;
    this._addFiles(files);
  }

  _onDragIntoWindow(e) {
    // Expand the drop area when any file is being dragged in the window.
    if (!this._eventGetFiles(e).length) return;
    e.preventDefault();
    this.expanded = true;
  }

  _onDragOutOfWindow(e) {
    // Unexpand the component when a file is no longer being dragged.
    if (!this._eventGetFiles(e).length) return;
    e.preventDefault();
    this.expanded = false;
  }

  _eventGetFiles(e) {
    if (!e || !e.dataTransfer) return [];
    const dt = e.dataTransfer;

    if (dt.items && dt.items.length) {
      const filteredItems = [...dt.items].filter(
        (item) => item.kind === 'file');
      return filteredItems.map((item) => item.getAsFile());
    }

    return [...dt.files];
  }

  _loadLocalFile(f) {
    // The FileReader API only accepts callbacks for asynchronous handling,
    // so it's easier to use Promises here. But by wrapping this logic
    // in a Promise, we can use async/await in outer code.
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onloadend = () => {
        resolve({filename: f.name, content: btoa(r.result)});
      };
      r.onerror = () => {
        reject(r.error);
      };

      r.readAsBinaryString(f);
    });
  }

  _filesChanged(e) {
    const input = e.currentTarget;
    if (!input.files) return;
    this._addFiles(input.files);
  }

  _addFiles(newFiles) {
    if (!newFiles) return;
    // Spread files to convert it from a FileList to an Array.
    const files = [...newFiles].filter((f1) => {
      const matchingFile = this.files.some((f2) => this._filesMatch(f1, f2));
      return !matchingFile;
    });

    this.files = this.files.concat(files);
  }

  _filesMatch(a, b) {
    // NOTE: This function could return a false positive if two files have the
    // exact same name, lastModified time, size, and type but different
    // content. This is extremely unlikely, however.
    return a.name === b.name && a.lastModified === b.lastModified
      && a.size === b.size && a.type === b.type;
  }

  _removeFile(e) {
    const target = e.currentTarget;

    // This should always be an int.
    const index = Number.parseInt(target.dataset.index);
    if (index < 0 || index >= this.files.length) return;

    this.files.splice(index, 1);

    // Trigger an update.
    this.files = [...this.files];
  }
}
customElements.define('mr-upload', MrUpload);
