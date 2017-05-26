(function() {
  'use strict';
  const archivePrefix =
      'https://storage.googleapis.com/chromium-layout-test-archives/';

  Polymer({
    is: 'som-webkit-tests',
    properties: {
      builder: {
        type: Object,
        value: function() { return {}; },
      },
      testName: {
        type: String,
        value: '',
        observer: '_testNameChanged',
      },
      testType: String,
      actualUrls: {
        type: Array,
        value: [],
        observer: '_actualUrlsChanged',
      },
      expectedUrls: {
        type: Array,
        value: [],
        observer: '_expectedUrlsChanged',
      },
      _flakinessDashboardUrl: {
        type: String,
        computed: '_computeFlakinessDashboardUrl(testName, testType)',
      },
      diffUrls: {
        type: Array,
        value: [],
        observer: '_diffUrlsChanged',
      },
      allResultsUrl: {
        type: String,
        value: '',
      },
    },

    _actualUrlsChanged: function(urls) {
      this._emptyNode(this.$.actualIframes);
      urls.forEach(
          (url) => { this._appendIfExists(url, this.$.actualIframes); });
    },

    _expectedUrlsChanged: function(urls) {
      this._emptyNode(this.$.expectedIframes);
      urls.forEach(
          (url) => { this._appendIfExists(url, this.$.expectedIframes); });
    },

    _diffUrlsChanged: function(urls) {
      this._emptyNode(this.$.diffIframes);
      urls.forEach((url) => { this._appendIfExists(url, this.$.diffIframes); });
    },

    _emptyNode: function(node) {
      while (node.childNodes.length) {
        node.removeChild(node.firstChild);
      }
    },

    _appendIfExists: function(url, el) {
      // Check to see if the URL exists before adding it to the page.
      fetch(url, {method: 'HEAD'}).then((response) => {
        if (response.status === 200) {
          this._attachIFrame(url, el);
        }
      });
    },

    _attachIFrame: function(url, el) {
      // This is to avoid polluting the browser navigation history with
      // the contents of IFrames. By setting the iframe src *before* adding
      // the IFrame to the DOM, we avoid adding src to the top level nav
      // history.
      let iframe = document.createElement('iframe');
      iframe.style.border = '0';
      iframe.style.flexGrow = 1;
      iframe.src = url;
      el.appendChild(iframe);
    },

    _computeFlakinessDashboardUrl: function(testName, testType) {
      testType = testType ? testType : 'webkit_tests';
      return 'https://test-results.appspot.com/dashboards/' +
             'flakiness_dashboard.html#' +
             'tests=' + encodeURIComponent(testName) +
             '&testType=' + encodeURIComponent(testType);
    },

    _testNameChanged: function(testName) {
      if (!this.builder.name) {
        return;
      }
      let basePath = urlFmt.layoutTest(this.builder.name,
                                       this.builder.latest_failure, testName);

      // TODO: Think about replacing all of this with just an iframe to this
      // URL. It appears to contain all of the same information we want to
      // display here, and it doesn't try to do any guessing about what
      // test output files should exist
      this.allResultsUrl =
          urlFmt.layoutTestAll(this.builder.name, this.builder.latest_failure);

      // This will try loading every possible output file that might exist on
      // GCS and show only the ones that actually exist. It's hackish, but
      // there does not appear to be a better way to tell which tests map
      // to which outputs.
      this.actualUrls = [basePath + '-actual.png', basePath + '-actual.txt'];
      this.expectedUrls =
          [basePath + '-expected.png', basePath + '-expected.txt'];
      this.diffUrls = [
        basePath + '-diff.png', basePath + '-diff.txt',
        basePath + '-pretty-diff.html', basePath + '-wdiff.html',
        basePath + '-overlay.html'
      ];
    },
  });
})();
