Documenting in infra/
=====================

Documentation in `infra/` should cover these subjects:

- Introductory material, to help newcomers use and contribute to the codebase.
- design documents, explaining decisions and overall structure. The point of
  these docs is to give a high-level view of the organisation and inner working.
- reference documentation, extracted from docstrings

Note:
  We only cover Python right now, more to come for Go and Javascript. Feel free
  to nag pgervais@ and/or contribute.


How to write docstrings
-----------------------
For documentation extracted from docstrings to show up properly in the final
html page, some minimal formatting rules should be followed. Several conventions
can be used, we chose to use the 'Google' one (as defined
`here <http://sphinxcontrib-napoleon.readthedocs.org/en/latest/>`_).

Here's a minimalistic example::

  def my_pretty_func(arg1, arg2, kwarg1=None):
    """One-line description of what the function does.

    Multiple-line description of what the function does. Try not to repeat
    what is in the one-line description or in the argument descriptions below.

    Args:
      arg1 (str): first argument.
      arg2 (int): second argument, not the same type.

    Keyword Args:
      kwarg1 (float): optional argument

    Returns:
      ret (string): an awesome value

    Raises:
      ValueError: if arg1 and arg2 are not awesome values.

    See Also:
      :func:`my_other_pretty_func` does another pretty cool thing.
    """

Hyperlinking is really important, and Sphinx provides some facilities. The
`:func:` syntax allows you to hyperlink to the doc for the specified entity.
You can also use `:class:` and others. The full list is
`here <http://sphinx-doc.org/domains.html#python-roles>`_.
General information about hyperlinking in Sphinx can be found on `this page
<http://sphinx-doc.org/markup/inline.html#xref-syntax>`_.

For more examples, you can use the `[source]` link that shows up on the right of
reference doc pages to see the source it was built from. See e.g.
:doc:`reference/infra.libs/`.

Writing in-depth articles
-------------------------

Detailing higher-level concepts and explaining technical choices require longer
documents. They are thus not contained within docstrings, but written as
independent rst files, stored in ``doc/source``. When creating a new page,
remember to add a link to it in the top-level ``index.rst`` file.

As with docstrings, a great way to learn the rst syntax is to use the 'Show
source' links located on the side panel. They link to the raw file from which
the html was generated.


The compilation / deployment pipeline
=====================================

Inserting documentation taken from docstrings is a simple matter of adding
something like::

   .. automodule:: infra
       :members:
       :undoc-members:
       :show-inheritance:

in an rst file. The above snippet includes all docstring found at the root of
the infra package. To insert documentation for ``infra.libs``, you have to add
another section like this somewhere else. Given the highly hierarchical nature
of the ``infra`` package, this would be a pain to maintain manually, so we're
using the ``sphinx-apidoc`` command that generates stub files containing only
``automodule`` directive. These files could be checked-out in the repository,
but it has been chosen *not to do it*, to simplify the process. Missing files
are generated on the fly by ``docgen.py``.

``docgen.py`` then runs ``sphinx-build``, which:

- reads files in ``doc/source``
- extracts docstrings
- compiles html pages that are written in ``doc/html``

The main entry point is and should remain ``doc/html/index.html``.

When modifying the documentation, it is highly recommended to compile it
locally, and check that the rendered output is what you expected. The ReST can
be surprising at times.

Deploying the documentation to the web is done automatically by a builder
running on the Chrome infrastructure. Thus all you have to do is to get your
changes committed. The builder is currently running on a non-public waterfall,
but the recipe is public and located in `build/
<http://src.chromium.org/viewvc/chrome/trunk/tools/build/scripts/slave/recipes/infra/>`_
All it does is remove existing rendered files, compile them again, and copy the
content of ``doc/html`` to a Cloud Storage bucket at
`gs://chromium-infra-docs/infra
<https://storage.googleapis.com/chromium-infra-docs/infra/index.html>`_.

