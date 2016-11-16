# libs

The [libs](libs) module is for shared & standalone code that has no dependency
on AppEngine but just a standard python library. However, it should also be
AppEngine-compatible -- can be run on AppEngine. For example, the code must not
write to the file system (using of os.path is OK though).

# How to use?

Create a symbolic link to [libs](libs) under a directory PARENT\_DIR, and ensure
that PARENT\_DIR is added to sys.path or PYTHONPATH.

The usage would look like: `from libs import API_MODULE_NAME`
