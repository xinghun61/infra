.. infra documentation master file, should at least contain the root 
   `toctree` directive.

Chrome Infra infra/ Repository
==============================
This documentation describes the new (as of September 2014) repository
containing the public code for the Chrome infrastructure: infra/. The old
repository is called build/.

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
* :doc:`structure` - describes the general repository layout
* :doc:`contributing`


Contributer's Guides
--------------------

* How to add a new tool - also gives example usage of
  :doc:`reference/infra.libs`
* How to develop an appengine app in infra/
* How to handle authentication


Technical Background
--------------------

This section (will) explains some technical choices.

* Testing in infra/ - tools used, how and why.
* Dependency handling - how it works and why it's structured this way.
* Documentation - what and how to document.

Indices and Tables
------------------

.. toctree::
   :maxdepth: 2

   installation
   usage
   structure
   contributing
   reference/modules

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


