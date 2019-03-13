// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

export default class MrFlipper extends HTMLElement {

  static is() {
    return 'mr-flipper';
  }

  connectedCallback() {
    this.current = null;
    this.totalCount = null;
    this.prevUrl = null;
    this.nextUrl = null;
    this.listUrl = null;
    this.showCounts = false;

    // Set up DOM.
    const shadowRoot = this.attachShadow({mode: 'open'});
    shadowRoot.appendChild(this._template().content.cloneNode(true));

    // References to DOM nodes for convenience.
    this.countsEl = shadowRoot.querySelector('div.counts');
    this.currentIndexEl = shadowRoot.querySelector('span.current-index');
    this.totalCountEl = shadowRoot.querySelector('span.total-count');
    this.prevUrlEl = shadowRoot.querySelector('a.prev-url');
    this.nextUrlEl = shadowRoot.querySelector('a.next-url');
    this.listUrlEl = shadowRoot.querySelector('a.list-url');

    if (location.search) {
      this.listUrlEl.style.visibility = 'visible';
      this.listUrlEl.href = `detail/list${location.search}`;
    }

    this.fetchFlipperData();
  }

  // Eventually this should be replaced with pRPC.
  fetchFlipperData() {
    const options = {
      credentials: 'include',
      method: 'GET',
    };
    fetch(`detail/flipper${location.search}`, options).then(
      (response) => response.text()
    ).then(
      (responseBody) => {
        let responseData;
        try {
          // Strip XSSI prefix from response.
          responseData = JSON.parse(responseBody.substr(5));
        } catch (e) {
          console.error(`Error parsing JSON response for flipper: ${e}`);
          return;
        }

        this._updateTemplate(responseData);
      }
    );
  }

  _updateTemplate(data) {
    const curIndex = data.cur_index + 1;
    if (curIndex && data.total_count) {
      this.countsEl.style.visibility = 'visible';
    } else {
      // Hide, no updates needed.
      this.countsEl.style.visibility = 'hidden';
      return;
    }

    // Add one to index since we display cardinal number in UI.
    this.currentIndexEl.innerText = curIndex;
    this.totalCountEl.innerText = data.total_count;

    if (data.prev_url) {
      this.prevUrlEl.style.visibility = 'visible';
      this.prevUrlEl.href = data.prev_url;
    } else {
      this.prevUrlEl.style.visibility = 'hidden';
    }

    if (data.next_url) {
      this.nextUrlEl.style.visibility = 'visible';
      this.nextUrlEl.href = data.next_url;
    } else {
      this.nextUrlEl.style.visibility = 'hidden';
    }

    if (data.list_url) {
      this.listUrlEl.style.visibility = 'visible';
      this.listUrlEl.href = data.list_url;
    } else {
      this.listUrlEl.style.visibility = 'hidden';
    }
  }

  _template() {
    const tmpl = document.createElement('template');
    // Warning: do not interpolate any variables into the below string.
    // Also don't use innerHTML anywhere other than in this specific scenario.
    tmpl.innerHTML = `
      <style>
        :host {
          display: flex;
          justify-content: center;
          flex-direction: column;
          // TODO(zhangtiff): Replace this with a global link color variable.
          --mr-flipper-link-color: var(--chops-link-color);
        }
        a {
          display: block;
          padding: 0.25em 0;
          color: var(--mr-flipper-link-color);
        }
        a, div {
          flex: 1;
          white-space: nowrap;
          padding: 0 2px;
        }
        .counts {
          padding: 0 16px;
        }
        .counts, a.prev-url, a.next-url, a.list-url {
          /* Initially not shown */
          visibility: hidden;
        }
        .row {
          display: flex;
          align-items: baseline;
          text-align: center;
          flex-direction: row;
        }
        @media (max-width: 960px) {
          :host {
            display: inline-block;
          }
        }
      </style>

      <div class="row">
        <a href="" title="Prev" class="prev-url">
          &lsaquo; Prev
        </a>
        <div class="counts">
          <span class="current-index">&nbsp;</span>
          <span>of</span>
          <span class="total-count">&nbsp;</span>
        </div>
        <a href="" title="Next" class="next-url">
          Next &rsaquo;
        </a>
      </div>
      <div class="row">
        <a href="" title="Back to list" class="list-url">
          Back to list
        </a>
      </div>
    `;
    return tmpl;
  }
}

window.customElements.define(MrFlipper.is(), MrFlipper);
