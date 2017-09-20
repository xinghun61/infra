# chops-ui

Design Doc: go/chops-ui

This directory contains Polymer Web Components that are meant to be shared
by Chrome Operations' application frontends.

TBD: The method of importing these elements and their dependencies for use.

## Documenting elements
Please add demos and documentation for elements as described in the [polymer docs](https://www.polymer-project.org/2.0/docs/tools/documentation#document-an-element).

After each documentation change please update analysis.json by running:
polymer analyze > analysis.json

To check that your demo and documentation are working and correct:
polymer serve

and visit http://localhost:XXXX/components/chops-ui/docs.html