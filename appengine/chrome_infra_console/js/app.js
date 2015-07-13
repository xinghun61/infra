/*
 Copyright 2015 The Chromium Authors. All rights reserved.
 Use of this source code is governed by a BSD-style license that can be
 found in the LICENSE file.
 */

(function(document) {
  'use strict';

  // Grab a reference to our auto-binding template
  // and give it some initial binding values.
  var app = document.querySelector('#app');

  // Close drawer after menu item is selected if drawerPanel is narrow.
  app.onMenuSelect = function() {
    var drawerPanel = document.querySelector('#paperDrawerPanel');
    if (drawerPanel.narrow) {
      drawerPanel.closeDrawer();
    }
  };

  app.homeClicked = function() {
    var pages = document.querySelector('iron-pages');
    pages.selected = 0 ;
  };

  app.helpClicked = function() {
    var pages = document.querySelector('iron-pages');
    pages.selected = 1 ;
  };

  app.feedbackClicked = function() {
    var pages = document.querySelector('iron-pages');
    pages.selected = 2 ;
  };

})(document);
