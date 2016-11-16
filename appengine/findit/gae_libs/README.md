# gae_libs

The [gae\_libs](gae_libs) module is for shared code that depends on App Engine
APIs (gae is short for Google App Engine), eg: an NDB model that supports
keeping multiple versions of the same information like configuration.

It also depends on the sibling [libs](libs) module, and provides gae wrappers
for the code there, e.g., a Gitiles client with data cached in memcache on App
Engine.

# How to use?

Create symbolic links to both [gae\_libs](gae_libs) and [libs](libs) in the same
directory PARENT\_DIR, and ensure that PARENT\_DIR is in sys.path or PYTHONPATH.

The usage would look like: `from gae_libs import API_MODULE_NAME`
