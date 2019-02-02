/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

const path = require('path');

module.exports = {
  entry: {
    'elements/mr-app/mr-app': './elements/mr-app/mr-app.js',
    'elements/chdir/mr-profile-page/mr-profile-page': './elements/chdir/mr-profile-page/mr-profile-page.js',
    'elements/mr-bulk-approval-update/mr-bulk-approval-update': './elements/mr-bulk-approval-update/mr-bulk-approval-update.js',
  },
  devtool: 'inline-source-map',
  resolve: {
    extensions: ['.js'],
  },
  output: {
    filename: '[name].min.js',
    path: path.resolve(__dirname),
  },
};
