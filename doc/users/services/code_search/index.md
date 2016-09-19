# Code Search for Chromium

Search, view, and navigate Chromium code:

* [cs.chromium.org](http://cs.chromium.org): Production service.
* [cs-staging.chromium.org](http://staging-cs.chromium.org): Staging service.

## Current Offering

The service currently supports the following:

* **Code covered**, see [build/scripts/slave/recipes/chromium\_codesearch.py](https://cs.chromium.org/chromium/build/scripts/slave/recipes/chromium_codesearch.py) for included repos.
* **Search** for all covered code.
* **Code Visualization**, that is, syntax highlighting and formatting, for C++, Python,
  JavaScript, Java, ObjC, Go, and Proto files.
* **Cross-references**, that is, use-def navigational links, for C++/Linux.

If you experience problems with code search, please report issues to [chrome-troopers].
If you have a feature request, please file a bug in the [Codesearch component].

## Current Work and Road Map

Our first priority is to keep the current offering stable, see
[stability bugs].

Second to stability, we want to improve the service. For the
next generation, we are working on:

* Git integration (see [git bugs]),
* C++ cross references on more platforms (see [xrefs bugs]),
* Performance improvements in the backend.

[chrome-troopers]: https://chromium.googlesource.com/infra/infra/+/master/doc/users/contacting_troopers.md
[Codesearch component]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=component%3AInfra%3ECodesearch&sort=status&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified&x=m&y=releaseblock&cells=ids
[stability bugs]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=component%3AInfra%3ECodesearch+label%3AStability&sort=type&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified+Type&x=m&y=releaseblock&cells=ids
[git bugs]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=component%3AInfra%3ECodesearch+label%3AGit&sort=type&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified+Type&x=m&y=releaseblock&cells=ids
[xrefs bugs]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=component%3AInfra%3ECodesearch+label%3AXrefs&sort=type&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified+Type&x=m&y=releaseblock&cells=ids

