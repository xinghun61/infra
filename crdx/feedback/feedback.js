// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window, document) {
  'use strict';

  var css = `
    .__crdxFeedbackButton {
      position: fixed;
      bottom: 32px;
      right: 24px;
      width: 32px;
      height: 32px;
      z-index: 8675309; /* Jenny */
      transition: opacity .2s;
      opacity: .4;
      background-image: url('https://storage.googleapis.com/crdx-feedback.appspot.com/icon.png');
      background-size: cover;
    }
    .__crdxFeedbackButton:hover {
      opacity: .75;
    }
  `;

  var el = document.createElement('style');
  el.appendChild(document.createTextNode(css));
  document.head.appendChild(el);

  var button = document.createElement('a');
  button.classList.add('__crdxFeedbackButton');
  button.target = '_blank';

  // document.body may not exist yet.
  if (!document.body) {
    window.addEventListener('load', function() {
      document.body.appendChild(button);
    });
  } else {
    document.body.appendChild(button);
  }

  var crdx = window[window.CrDXObject] || {};
  var queue = crdx.q || [];

  crdx = function() {
    if (typeof crdx[arguments[0]] === 'function') {
      crdx[arguments[0]].apply(null, Array.from(arguments).slice(1));
    }
  };

  crdx.setFeedbackButtonLink = function(href) {
    button.href = href;
  };

  queue.forEach(function(args) { crdx.apply(null, args); });

  window[window.CrDXObject] = crdx;
})(window, document);
