const path = require('path');

module.exports = {
  entry: ['./src/navbar.js', './src/rotacreate.js', './src/rotashiftswap.js', './src/rotaoncall.js', './src/rotamember.js',
    './src/constants.js', './src/rotashiftcurrent.js', './src/rotashifthistory.js', './src/rotashiftgenerate.js'],
  devtool: 'inline-source-map',
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        exclude: /node_modules/
      }
    ]
  },
  resolve: {
    extensions: [ '.js' ]
  },
  output: {
    filename: 'bundle.js',
    path: path.resolve(__dirname, 'dist')
  }
};
