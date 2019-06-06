// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

const path = require('path');

module.exports = {
  entry: {
    'elements/chops-button': './elements/chops-button/chops-button.js',
    'elements/chops-checkbox': './elements/chops-checkbox/chops-checkbox.js',
    'elements/chops-header': './elements/chops-header/chops-header.js',
    'elements/chops-input': './elements/chops-input/chops-input.js',
    'elements/chops-loading': './elements/chops-loading/chops-loading.js',
    'elements/chops-login': './elements/chops-login/index.js',
    'elements/chops-radio': './elements/chops-radio/chops-radio.js',
    'elements/chops-radio-group':
      './elements/chops-radio-group/chops-radio-group.js',
    'elements/chops-signin': './elements/chops-signin/index.js',
    'elements/chops-switch': './elements/chops-switch/chops-switch.js',
    'elements/chops-tab': './elements/chops-tab/chops-tab.js',
    'elements/chops-tab-bar': './elements/chops-tab-bar/chops-tab-bar.js',
    'elements/chops-textarea': './elements/chops-textarea/chops-textarea.js',
  },
  mode: 'development',
  resolve: {
    modules: ['node_modules', 'elements'],
    alias: {
      '@chopsui/chops-checkbox': path.resolve(
        'elements/chops-checkbox/chops-checkbox.js'),
    },
  },
};
