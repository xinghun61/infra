'use strict';

const HELP_PATH_REGEX = /\/help\/(\w+)\/?$/;

class CgApp extends Polymer.Element {

  static get is() {
    return 'cg-app';
  }

  static get properties() {
    return {
      _error: Object,
      _descriptor: Object,
      _helpFilePath: {
        type: String,
        computed: '_computeHelpFilePath(_path)',
      },
      _loading: Boolean,
      _path: String,
      _title: {
        type: String,
        observer: '_titleChanged',
      },
    };
  }

  _computeHelpFilePath(path) {
    const matches = path.match(HELP_PATH_REGEX);
    if (!matches || matches.length <= 1) return '';

    return `/docs/${matches[1]}.md`;
  }

  _titleChanged(title) {
    window.document.title = `ChOpsUI Gallery - ${title}`;
  }
}

customElements.define(CgApp.is, CgApp);
