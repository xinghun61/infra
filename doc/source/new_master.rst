Setting Up a New Master
=======================

To set up a new master, you need three ports. File an `Infra-Labs ticket`_
requesting ports for a new master.  These port numbers will need to go in the
``builders.pyl`` config file later.

Then create a new master directory in ``build/masters`` or
``build_internal/masters`` depending on whether this is a Google internal
master.::

  $ cd $BUILD_DIR/masters
  $ mkdir master.foo.bar
  $ cd master.foo.bar

Create a ``builders.pyl`` file describing the builders on this master.  Look at
this `example builders.pyl`_ for reference. Put the port numbers you received
from Labs into this file.  You will also need slaves allocated for all your
builders, and they will be configured in this file.::

  $ cp $BUILD_DIR/masters/masters.chromium.mojo/builders.pyl .
  <edit builders.pyl to taste>

After this file exists, you can use ``buildbot-tool`` to generate the rest of
the master configuration.::

  $ $BUILD_DIR/scripts/tools/buildbot-tool gen `pwd`

You'll also need to add your new master to the long list in
``$BUILD_DIR/tests/masters_test.py``.::

  # Add this line to $BUILD_DIR/tests/masters_test.py next to the other lines
  # that look like this.
  'master.foo.bar': 'FooBar',

You can find the class name ``FooBar`` in the ``master_site_config.py`` that
was generated in your master directory.

Commit what you have, then file another `Infra-Labs ticket`_ asking for the
appropriate URLs to be set up for your master.

.. _`Infra-Labs ticket`: https://code.google.com/p/chromium/issues/entry?labels=Type-Bug,Pri-2,Infra-Labs
.. _`example builders.pyl`: http://src.chromium.org/viewvc/chrome?revision=293411&view=revision
