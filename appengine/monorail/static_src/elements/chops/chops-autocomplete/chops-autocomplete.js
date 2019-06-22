// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

const DELIMITER_REGEX = /[^a-z0-9]+/i;
const DEFAULT_REPLACER = (input, value) => input.value = value;
const DEFAULT_MAX_COMPLETIONS = 200;

/**
 * `<chops-autocomplete>` shared autocomplete UI code that inter-ops with
 * other code.
 *
 * chops-autocomplete inter-ops with any input element, whether custom or
 * native that can receive change handlers and has a 'value' property which
 * can be read and set.
 *
 * @customElement
 */
export class ChopsAutocomplete extends LitElement {
  static get styles() {
    return css`
      :host {
        position: relative;
      }
      table {
        padding: 0;
        min-width: 100px;
        max-height: 300px;
        overflow: auto;
        font-size: var(--chops-main-font-size);
        color: var(--chops-link-color);
        position: absolute;
        top: 90%;
        background: white;
        border: var(--chops-accessible-border);
        z-index: 999;
        box-shadow: 2px 3px 8px 0px hsla(0, 0%, 0%, 0.3);
        border-spacing: 0;
        border-collapse: collapse;
      }
      tr {
        cursor: pointer;
        transition: background 0.2s ease-in-out;
      }
      tr[data-selected] {
        background: var(--chops-blue-100);
      }
      td {
        padding: 0.25em 8px;
        white-space: nowrap;
      }
    `;
  }

  render() {
    const completions = this.completions;
    return html`
      <slot @slotchange=${this._registerInputElement}></slot>
      <table
        ?hidden=${!completions.length}
      >
        <tbody>
          ${completions.map((completion, i) => html`
            <tr
              ?data-selected=${i === this._selectedIndex}
              data-index=${i}
              data-value=${completion}
              @mouseover=${this._hoverCompletion}
              @mousedown=${this._clickCompletion}
            >
              <td class="completion">
                ${this._renderCompletion(completion)}
              </td>
              <td class="docstring">
                ${this._renderDocstring(completion)}
              </td>
            </tr>
          `)}
        </tbody>
      </table>
    `;
  }

  _renderCompletion(completion) {
    const matchDict = this._matchDict;

    if (!(completion in matchDict)) return completion;

    const {index, matchesDoc} = matchDict[completion];

    if (matchesDoc) return completion;

    const prefix = this._prefix;
    const start = completion.substr(0, index);
    const middle = completion.substr(index, prefix.length);
    const end = completion.substr(index + prefix.length);

    return html`${start}<b>${middle}</b>${end}`;
  }

  _renderDocstring(completion) {
    const matchDict = this._matchDict;
    const docDict = this.docDict;

    if (!completion in docDict) return '';

    const doc = docDict[completion];

    if (!(completion in matchDict)) return doc;

    const {index, matchesDoc} = matchDict[completion];

    if (!matchesDoc) return doc;

    const prefix = this._prefix;
    const start = doc.substr(0, index);
    const middle = doc.substr(index, prefix.length);
    const end = doc.substr(index + prefix.length);

    return html`${start}<b>${middle}</b>${end}`;
  }

  static get properties() {
    return {
      /**
       * Array of strings for possible autocompletion values.
       */
      strings: {type: Array},
      /**
       * A dictionary containing optional doc strings for each autocomplete
       * string.
       */
      docDict: {type: Object},
      /**
       * An optional function to compute what happens when the user selects
       * a value.
       */
      replacer: {type: Object},
      /**
       * An Array of the currently suggested autcomplte values.
       */
      completions: {type: Array},
      /**
       * Maximum number of completion values that can display at once.
       */
      max: {type: Number},
      /**
       * Dict of locations of matched substrings. Value format:
       * {index, matchesDoc}.
       */
      _matchDict: {type: Object},
      _selectedIndex: {type: Number},
      _prefix: {type: String},
      _forRef: {type: Object},
      _boundFocusHandler: {type: Object},
      _boundNavigateCompletions: {type: Object},
      _boundKeyInputHandler: {type: Object},
    };
  }

  constructor() {
    super();

    this.strings = [];
    this.docDict = {};
    this.completions = [];
    this.max = DEFAULT_MAX_COMPLETIONS;

    this._matchDict = {};
    this._selectedIndex = -1;
    this._prefix = '';
    this._boundFocusHandler = this._focusHandler.bind(this);
    this._boundKeyInputHandler = this._keyInputHandler.bind(this);
    this._boundNavigateCompletions = this._navigateCompletions.bind(this);
  }

  disconnectedCallback() {
    super.disconnectedCallback();

    this._disconnectAutocomplete(this._forRef);
  }

  /**
   * Changes the input's value according to the rules of the replacer function.
   *
   * @param {string} value - the value to swap in.
   * @return {undefined}
   */
  completeValue(value) {
    if (!this._forRef) return;

    const replacer = this.replacer || DEFAULT_REPLACER;
    replacer(this._forRef, value);

    this.hideCompletions();
  }

  /**
   * Computes autocomplete values matching the current input in the field.
   *
   * @param {boolean} includeDefault - Whether to include non-matching values.
   * @return {boolean} Whether any completions were found.
   */
  showCompletions(includeDefault) {
    if (!this._forRef) {
      this.hideCompletions();
      return false;
    }
    this._prefix = this._forRef.value.trim().toLowerCase();
    // Always select the first completion by default when recomputing
    // completions.
    this._selectedIndex = 0;

    const matchDict = {};
    const accepted = [];
    const rejected = [];
    matchDict;
    for (let i = 0; i < this.strings.length
        && accepted.length < this.max; i++) {
      const s = this.strings[i];
      let matchIndex = this._matchIndex(this._prefix, s);
      let matches = matchIndex >= 0;
      if (matches) {
        matchDict[s] = {index: matchIndex, matchesDoc: false};
      } else if (s in this.docDict) {
        matchIndex = this._matchIndex(this._prefix, this.docDict[s]);
        matches = matchIndex >= 0;
        if (matches) {
          matchDict[s] = {index: matchIndex, matchesDoc: true};
        }
      }
      if (matches) {
        accepted.push(s);
      } else if (rejected.length < this.max) {
        rejected.push(s);
      }
    }

    this._matchDict = matchDict;

    if (includeDefault) {
      const maxRejected = this.max - accepted.length;
      if (rejected.length > maxRejected) {
        rejected = rejected.slice(0, maxRejected);
      }
      this.completions = [...accepted, ...rejected];
    } else {
      this.completions = accepted;
    }

    return !!this.completions.length;
  }

  _matchIndex(prefix, s) {
    const matchStart = s.toLowerCase().indexOf(prefix.toLocaleLowerCase());
    if (matchStart === 0
        || (matchStart > 0 && s[matchStart - 1].match(DELIMITER_REGEX))) {
      return matchStart;
    }
    return -1;
  }

  hideCompletions() {
    this.completions = [];
    this._prefix = '';
    this._selectedIndex = -1;
  }

  _registerInputElement(e) {
    const nodes = e.target.assignedNodes();

    if (nodes && nodes.length > 0) {
      this._forRef = nodes.find(
        (el) => (el.tagName || '').toUpperCase() === 'INPUT');
      this._connectAutocomplete(this._forRef);
    } else {
      this._forRef = null;
    }
  }

  _hoverCompletion(e) {
    const target = e.currentTarget;

    if (!target.dataset || !target.dataset.index) return;

    const index = Number.parseInt(target.dataset.index);
    if (index >= 0 && index < this.completions.length) {
      this._selectedIndex = index;
    }
  }

  _clickCompletion(e) {
    e.preventDefault();
    const target = e.currentTarget;
    if (!target.dataset || !target.dataset.value) return;

    this.completeValue(target.dataset.value);
  }

  _focusHandler(e) {
    const target = e.target;

    // Check if the input is focused or not.
    if (target.matches(':focus')) {
      this.showCompletions(true);
    } else {
      this.hideCompletions();
    }
  }

  _navigateCompletions(e) {
    const completions = this.completions;
    if (!completions.length) return;

    switch (e.key) {
      case 'ArrowUp':
        e.preventDefault();
        this._selectedIndex -= 1;
        if (this._selectedIndex < 0) {
          this._selectedIndex = completions.length - 1;
        }
        break;
      case 'ArrowDown':
        e.preventDefault();
        this._selectedIndex += 1;
        if (this._selectedIndex >= completions.length) {
          this._selectedIndex = 0;
        }
        break;
      case 'Enter':
      // TODO(zhangtiff): Add Tab to this case as well once all issue detail
      // inputs use chops-autocomplete.
        e.preventDefault();
        if (this._selectedIndex >= 0
            && this._selectedIndex <= completions.length) {
          this.completeValue(completions[this._selectedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        this.hideCompletions();
        break;
    }
  }

  _keyInputHandler(e) {
    if (['Enter', 'Tab', 'ArrowUp', 'ArrowDown', 'Escape'].includes(
      e.key)) return;
    this.showCompletions();
  }

  _connectAutocomplete(node) {
    if (!node) return;

    node.addEventListener('keyup', this._boundKeyInputHandler);
    node.addEventListener('keydown', this._boundNavigateCompletions);
    node.addEventListener('focus', this._boundFocusHandler);
    node.addEventListener('blur', this._boundFocusHandler);
  }

  _disconnectAutocomplete(node) {
    if (!node) return;

    node.removeEventListener('keyup', this._boundKeyInputHandler);
    node.removeEventListener('keydown', this._boundNavigateCompletions);
    node.removeEventListener('focus', this._boundFocusHandler);
    node.removeEventListener('blur', this._boundFocusHandler);
  }
}
customElements.define('chops-autocomplete', ChopsAutocomplete);
