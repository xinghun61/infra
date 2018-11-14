'use strict';

/**
 * `<mr-bug-link>`
 *
 * Displays a link to a bug.
 *
 */
class MrBugLink extends Polymer.Element {
  static get is() {
    return 'mr-bug-link';
  }

  static get properties() {
    return {
      issue: Object,
      isClosed: {
        type: Boolean,
        reflectToAttribute: true,
      },
      projectName: String,
    };
  }

  _hideProjectName(mainProjectName, localProjectName) {
    if (!mainProjectName || !localProjectName) return true;
    return mainProjectName.toLowerCase() === localProjectName.toLowerCase();
  }
}
customElements.define(MrBugLink.is, MrBugLink);
