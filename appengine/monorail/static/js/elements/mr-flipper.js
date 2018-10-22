// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is govered by a BSD-style
// license that can be found in the LICENSE file or at
// https://developers.google.com/open-source/licenses/bsd

class MrFlipper extends HTMLElement {

  static is() {
    return 'mr-flipper';
  }

  constructor() {
    super();
    this.current = null;
    this.totalCount = null;
    this.prevUrl = null;
    this.nextUrl = null;
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

    this.fetchFlipperData();
  }

  // Eventually this should be replaced with pRPC.
  async fetchFlipperData() {
    const options = {
      credentials: 'include',
      method: 'GET',
    };
    const response = await fetch(`detail/flipper${location.search}`, options);
    const responseBody = await response.text();
    let responseData;
    try {
      // Strip XSSI prefix from response.
      responseData = JSON.parse(responseBody.substr(5));
    } catch {
      return;
    }

    this._updateTemplate(responseData);
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
  }

  _template(currentIndex, totalCount, prevUrl, nextUrl) {
    const tmpl = document.createElement('template');
    // Warning: do not interpolate any variables into the below string.
    // Also don't use innerHTML anywhere other than in this specific scenario.
    tmpl.innerHTML = `
      <style>
        .pagination {
          text-align: center;
          display: flex;
        }
        .pagination div {
          flex: 1;
          white-space: nowrap;
          padding: 0 2px;
        }
        .pagination div.counts, a.prev-url, a.next-url {
          /* Initially not shown */
          visibility: hidden;
        }
        @media (max-width: 960px) {
          .pagination {
            display: block;
          }
        }
      </style>

      <div class="pagination">
        <div>
          <a href="" title="Prev" class="prev-url">&lsaquo; Prev</a>
        </div>
        <div class="counts">
          <span class="current-index">&nbsp;</span>
          <span>of</span>
          <span class="total-count">&nbsp;</span>
        </div>
        <div>
          <a href="" title="Next" class="next-url">Next &rsaquo;</a>
        </div>
      </div>
    `;
    return tmpl;
  }

}

window.customElements.define(MrFlipper.is(), MrFlipper);
