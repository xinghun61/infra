'use strict';

/**
 * `<mr-attachment-gallery>`
 *
 * This creates a gallery of files for users to browse through.
 *
 */
class MrAttachmentGallery extends Polymer.Element {
  static get is() {
    return 'mr-attachment-gallery';
  }

  static get properties() {
    return {
      files: {
        type: Array,
        value: [
          {
            url: 'screenshot1.png',
            thumbUrl: 'screenshot1.png',
            fileSize: 146998,
          },
          {
            url: 'screenshot2.png',
            thumbUrl: 'screenshot2.png',
            fileSize: 58909,
          },
          {
            url: 'screenshot3.png',
            thumbUrl: 'screenshot3.png',
            fileSize: 227927,
          },
          {
            url: 'screenshot4.png',
            thumbUrl: 'screenshot4.png',
            fileSize: 45377,
          },
          {
            url: 'screenshot5.png',
            thumbUrl: 'screenshot5.png',
            fileSize: 514,
          },
          {
            url: 'gates-mock.json',
            viewUrl: '/p/chromium/issues/attachmentText?aid=341641',
            fileSize: 10000,
          },
        ],
      },
      _shownFile: {
        type: Object,
        computed: '_computeShownFile(files, _shownIndex)',
      },
      _shownText: String,
      _shownIndex: {
        type: Number,
        value: 0,
      },
    };
  }

  _unzeroIndex(i) {
    return i + 1;
  }

  _computeShownFile(files, i) {
    return files[i];
  }

  _displaySize(bytes) {
    if (bytes > 1000 * 1000) {
      return `${this._truncateDecimal(bytes / (1000 * 1000))} MB`;
    }
    if (bytes > 1000) {
      return `${this._truncateDecimal(bytes / 1000)} KB`;
    }
    return `${bytes} bytes`;
  }

  _truncateDecimal(n) {
    return Math.floor(n * 100) / 100;
  }

  _showFile(evt) {
    this._shownIndex = evt.currentTarget.dataset.index * 1;
    this.$.showFile.open();
  }

  _showNext() {
    this._shownIndex = (this._shownIndex + 1) % this.files.length;
  }

  _showPrev() {
    const l = this.files.length;
    this._shownIndex = (this._shownIndex - 1 + l) % l;
  }
}
customElements.define(MrAttachmentGallery.is, MrAttachmentGallery);
