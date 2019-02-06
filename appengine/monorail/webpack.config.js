/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

const path = require('path');
const webpack = require('webpack');
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin;

const config = {
  entry: {
    'elements/mr-app/mr-app': './elements/mr-app/mr-app.js',
    'elements/chdir/mr-profile-page/mr-profile-page': './elements/chdir/mr-profile-page/mr-profile-page.js',
    'elements/ezt-element-package': './elements/ezt-element-package.js',
  },
  devtool: 'inline-source-map',
  plugins: [],
  resolve: {
    extensions: ['.js'],
  },
  output: {
    filename: '[name].min.js',
    path: path.resolve(__dirname),
  },
};

module.exports = (env, argv) => {
  if (argv.mode === 'production') {
    // Settings for deploying JS to production.
    config.devtool = 'cheap-source-map';

    config.plugins = config.plugins.concat([
      new webpack.DefinePlugin(
        {'process.env.NODE_ENV': '"production"'}
      ),
    ]);
  }

  if (argv.analyze) {
    config.plugins.push(new BundleAnalyzerPlugin());
  }
  return config;
};
