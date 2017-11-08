# chops-ui

Design Doc: go/chops-ui

This directory contains Polymer Web Components that are meant to be shared
by Chrome Operations' application frontends.

TBD: The method of importing these elements and their dependencies for use.

## Documenting elements
Please add demos and documentation for elements as described in the [polymer docs](https://www.polymer-project.org/2.0/docs/tools/documentation#document-an-element).

Check that your demo and documentation are working and correct by running:

polymer analyze > static/analysis.json
eval `../../../../../env.py`
gae.py devserver -A chopsui-gallery

and visit http://localhost:8080/
