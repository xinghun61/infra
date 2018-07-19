// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window, document) {
  'use strict';

  var css = `
    .__crdxFeedbackButton {
      background-image: url('https://crdx-feedback.appspot.com.storage.googleapis.com/icon.png');
      background-size: cover;
      bottom: 32px;
      height: 32px;
      opacity: .4;
      position: fixed;
      right: 24px;
      text-decoration: none;
      transition: opacity .2s;
      width: 32px;
      z-index: 8675309; /* Jenny */
    }
    .__crdxFeedbackButton:hover,
    .__crdxFeedbackButton:hover::after {
      opacity: .75;
    }
    .__crdxFeedbackButton::after {
      color: #707070;
      content: "Feedback";
      font-size: 12px;
      left: 50%;
      opacity: 0;
      position: absolute;
      text-decoration: none;
      top: 28px;
      transform: translateX(-50%);
      transition: opacity .4s;
      -webkit-transform: translateX(-50%);
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
