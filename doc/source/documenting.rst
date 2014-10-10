Documenting in infra/
=====================

Documentation in `infra/` should cover these subjects:

- Introductory material, to help newcomers use and contribute to the codebase.
- design documents, explaining decisions and overall structure. The point of
  these docs is to give a high-level view of the organisation and inner working.
- reference documentation, extracted from docstrings

Note:
  We only cover Python right now, more to come for go and javascript. Feel free
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

