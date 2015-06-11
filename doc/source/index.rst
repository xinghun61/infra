.. infra documentation master file, should at least contain the root
   `toctree` directive.

Chrome Infra infra.git Repository
=================================
This documentation describes the new (as of March 2014) repository containing
the public code for the Chrome infrastructure: infra.git. The old repository is
called build/, and is based in SVN.

If you want to contribute to the Chromium browser, you're in the wrong place.
See
`http://dev.chromium.org/getting-involved <http://dev.chromium.org/getting-involved>`_
instead. You can find more information on the Chrome infrastructure
`here <http://dev.chromium.org/infra>`_.

If you cannot find what you're looking for here, feel free to ask questions on
infra-dev@chromium.org.

General Information
-------------------
* :doc:`installation`
* :doc:`usage` (start here)
* :doc:`structure` - describes the general repository layout.
* :doc:`deployment`
* :doc:`contributing`
* :doc:`reference/modules` - reference documentation, extracted from docstrings.

Usage Guides
------------

* :doc:`user_guide/new_master` - How to set up a new buildbot master.
* :doc:`user_guide/recipes` - Recipes user guide.
* :doc:`user_guide/builders_pyl` - The builders.pyl file format for masters.
* :doc:`master_auth`

Contributer's Guides
--------------------

* :doc:`documenting` - what and how to document, plus some technical information
  on the compilation/deployment pipeline.
* :doc:`testing` - tools used, how and why.
* :doc:`logging` - how logging works in infra.git.
* :doc:`flags` - how to process command-line arguments.
* :doc:`appengine` - How to develop an appengine app in infra.git

TBD:

* How to handle authentication
* How to add a new tool - also gives example usage of
  :doc:`reference/infra.libs`

Technical Background
--------------------

This section explains some technical choices.

* :doc:`bootstrap` - Dependency handling. How it works and why it's structured
  this way.

Other topics
-------------------
* :doc:`steps` - list of infra steps on waterfall and tryserver

Indices and Tables
------------------

.. toctree::
   :maxdepth: 2

   installation
   usage
   structure
   deployment
   contributing
   documenting
   steps
   reference/modules

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


