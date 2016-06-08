// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window, document) {
  'use strict';

  var el = document.createElement('link');
  el.rel = 'stylesheet';
  el.href = 'https://fonts.googleapis.com/icon?family=Material+Icons';
  el.addEventListener('load', function() { setButtonsVisible(true); });
  document.head.appendChild(el);

  var css = `
    .__crdxFeedbackButton {
      position: fixed;
      bottom: 32px;
      right: 24px;
      width: 32px;
      height: 32px;
      z-index: 8675309; /* Jenny */
      border-radius: 50%;
      transition: all .2s;
      text-decoration: none;
      opacity: .4;
      color: #666;
    }
    .__crdxFeedbackButton:hover {
      opacity: .6;
    }
    .__crdxFeedbackButton::before {
      display: block;
      padding: 4px;
      content: 'bug_report';
    }
  `;
  el = document.createElement('style');
  el.appendChild(document.createTextNode(css));
  document.head.appendChild(el);

  var button = document.createElement('a');
  button.classList.add('material-icons', '__crdxFeedbackButton');
  button.target = '_blank';

  function setButtonsVisible(visible) {
    button.style.display = visible ? null : 'none';
  }
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
    if (typeof crdx[arguments[0]] === "function") {
      crdx[arguments[0]].apply(null, Array.from(arguments).slice(1));
    }
  };

  crdx.setFeedbackButtonLink = function(href) {
    button.href = href;
  };

  queue.forEach(function(args) { crdx.apply(null, args); });

  window[window.CrDXObject] = crdx;
})(window, document);
