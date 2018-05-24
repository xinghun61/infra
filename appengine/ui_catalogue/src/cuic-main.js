// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * '<cuic-main>' is the main application element of the Chrome UI Catalog
 * viewer.
 * @customElement
 * @polymer
 */
class Main extends Polymer.Element {

  static get is() {
    return 'cuic-main';
  }

  static get properties() {
    return {
      page: {
        type: String,
        reflectToAttribute: true,
        observer: 'pageChanged_',
      },
      rootPattern: String,
      routeData: Object,
      subroute: String,
      queryParams: Object,
    };
  }

  static get observers() {
    return [
      'routePageChanged_(routeData.page, queryParams.screenshot_source)',
    ];
  }

  constructor() {
    super();

    // Get root pattern for app-route, for more info about `rootPath` see:
    // https://www.polymer-project.org/2.0/docs/upgrade#urls-in-templates
    this.rootPattern = (new URL(this.rootPath)).pathname;
  }

  routePageChanged_(page, screenshotSource) {
    // Polymer 2.0 will call with `undefined` on initialization.
    // Ignore until we are properly called with a string.
    if (page === undefined) {
      return;
    }
    if (screenshotSource) {
      // If no page was found in the route data, page will be an empty string.
      // Default to 'summary-view' in that case.
      this.set('page', page || 'cuic-summary-view');
    } else {
      // There was no location in the URL, aak the user where the data is.
      this.set('page','cuic-set-screenshot-source');
    }
  }

  pageChanged_(page) {
    // Load page import on demand. Show 404 page if fails
    const resolvedPageUrl = this.resolveUrl(page + '.html');
    Polymer.importHref(
        resolvedPageUrl, null, this.showPage404_.bind(this), true);
  }

  showPage404_() {
    this.page = 'cuic-view404';
  }

  screenshotSource() {
    return this.queryParams['screenshot_source'];
  }
}

window.customElements.define(Main.is, Main);

// Add standard feedback button (see
// https://chromium.googlesource.com/infra/infra/+/master/crdx/feedback)

(function(i,s,o,g,r,a,m){i['CrDXObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},a=s.createElement(o),
    m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
})(window,document,'script','https://storage.googleapis.com/crdx-feedback.appspot.com/feedback.js','crdx');

crdx('setFeedbackButtonLink', 'https://bugs.chromium.org/p/chromium/issues/entry?labels=Infra-DX&components=Infra>UICatalogue');
