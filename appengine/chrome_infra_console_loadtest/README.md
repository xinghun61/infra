# Test Polymer custom-elements with web component tester

# Configure node.js and npm to install in  $HOME/local as a global location
# Ensure ~/local/bin is on $PATH
    $ mkdir ~/local
    $ export PATH="$HOME/local/bin:$PATH"

# Install Node
    $ mkdir -p /tmp/node-install && cd /tmp/node-install
    $ curl http://nodejs.org/dist/node-latest.tar.gz | tar xz --strip-components=1
    $ ./configure --prefix=$HOME/local
    $ make install


#Install bower
		$ bower install

#At this point, you should have bower, node, npm in ~/local/bin

#Install wct. wct will be installed in ~/local/bin.
    $ npm install -g web-component-tester

#Create a wct.conf.js in the project directory
    $ emacs wct.conf.js
#Put following content into wct.conf.js

var WEB_COMPONENT= [
    {'/components/<basename>': '.'},
    {'/components': 'bower_components'},
    {'/components': '..'},
    {'/': '.'},
];
module.export ={
  verbose: true,
  suite: ['CUSTOM_ELEMENTS_FOLDER/**/test/*-test.html'],
};


#Run the following wct command inside the project directory
    $ wct CUSTOM_ELEMENTS_FOLDER/**/ElEMENT/test/*-test.html

