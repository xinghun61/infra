const path = require('path');
const CopyWebpackPlugin = require('copy-webpack-plugin');

module.exports = {
  entry: {
    'chops-header': './elements/chops-header/chops-header.js',
  },
  output: {
    filename: 'elements/[name]/[name].js',
    path: path.resolve(__dirname, 'dist'),
  },
  plugins: [
    new CopyWebpackPlugin([
      {from: 'demos/*'},
    ]),
  ],
  resolve: {
    extensions: ['.js'],
  },
  devServer: {
    contentBase: 'dist',
  },
};
