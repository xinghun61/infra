# Glossary

This is meant to be an easily searchable index for any term you may encounter
working on Chrome Infrastructure. Each entry should be no more than 2-3 sentences
and point to further documentation for deeper reading. Links in definitions
should be intra-document only; external links should be in a list below the
definition.

## Blink

Chrome's rendering engine. Forked from [WebKit](#WebKit) in 2013.

- [Source](https://chromium.googlesource.com/chromium/src/+/master/third_party/WebKit)

## Buildbot

A continuous integration framework that orchestrates builds. It is currently
being replaced by [LUCI](#LUCI).

- [Homepage](https://buildbot.net/)
- [Documentation](http://docs.buildbot.net/current/index.html)

## Buildbot Master

Coordinates [Buildbot](#Buildbot) builders. Examples of masters are chromium.webkit or
chromium.fyi.

## CQ

Short for [Commit Queue](#Commit-Queue).

## Chops

Short for Chrome Operations.

## Commit Queue

The service that takes the changes from CLs in [Gerrit](#Gerrit), tests them,
and if the tests pass, commits them onto the master branch of the Chromium
[git](#git) repository.

- [Documentation](/users/services/commit_queue/index.md)

## depot_tools

A set of command-line tools for Chromium development.

- [Man page](http://commondatastorage.googleapis.com/chrome-infra-docs/flat/depot_tools/docs/html/depot_tools.html)

## Gerrit

The current code review system.

Named after Dutch designer Gerrit Rietveld.

- Lives at https://chromium-review.googlesource.com

## git

The version control system used by all Chromium projects. Chromium transitioned from
Subversion in 2015.

## Gitiles

A front-end for viewing [git](#git) repositories on the web. You're probably reading
this on Gitiles. Chromium's Gitiles instance lives at https://chromium.googlesource.com.

## GN

A meta-build system that generates [Ninja](#Ninja) build files for building Chromium.
It replaced [GYP](#GYP).

- [GN README](https://chromium.googlesource.com/chromium/src/tools/gn/)

## Go

A compiled language used by all new projects in [Chops](#Chops). For example,
[LUCI](#LUCI) and [Sheriff-o-Matic](#Sheriff_o_Matic) are written in Go.

## Goma

A distributed compiler service that speeds up Chromium builds. Available only
for Googlers.

- [Setup instructions](https://www.chromium.org/developers/gn-build-configuration#TOC-Goma)

## GYP

A meta-build system for generating build files. Stands for Generate Your Project.
It was replaced by [GN](#GN) in 2016.

- [Documentation](https://gyp.gsrc.io/index.md)

## LogDog

A log aggregator for many [Chops](#Chops) services.

## LUCI

Stands for Layered Universal Continuous Integration. Primary features include
automatic sharding to run tests in O(1) time. Built as a replacement for
[Buildbot](#Buildbot).

- [GitHub project](https://github.com/luci)
- [Documentation (forthcoming)](http://luci.github.io/)

## Monorail

The Chromium bug tracker.

- Lives at https://bugs.chromium.org
- [Documentation](/appengine/monorail/README.md)

## Ninja

A build file format. Running [GN](#GN) will generate ninja files specific
to your architecture and OS.

## PolyGerrit

A [Polymer](#Polymer) front-end for [Gerrit](#Gerrit).

## Polymer

A front-end JavaScript library to increase the ergonomics of using web components.

## Python

Is the language much of infra's tools are built with, however new projects
must use [Go](#Go).

Python has a strong lineage in web platform infrastructure development. Much
of [WebKit](#WebKit), Mozilla, and [W3C](#W3C)'s infrastructure is written in
Python.

## Recipe

These are source files written in a [Python](#Python) DSL that describe what
steps a build should run. They are used both in [Buildbot](#Buildbot) and
[LUCI](#LUCI).

- [Documentation](/doc/users/recipes.md)

## Rietveld

The deprecated code review system Chromium used for many years.

Named after Dutch designer Gerrit Rietveld.

- https://codereview.chromium.org/

## Sheriff

A sheriff is someone who monitors builds to make sure the tree is always green.
There are sheriffs for different build [masters](#Buildbot-Master) in Chromium,
like GPU, V8, and Memory.

- See current sheriffs on the [waterfall](https://build.chromium.org/p/chromium/waterfall)

## Sheriff-o-Matic

A tool to make the lives of Chromium [Sherrifs](#Sheriff) easier.

- Lives at https://sheriff-o-matic.appspot.com

## Trooper

Refers to the current Chops oncall. Responsible for fielding pages and triaging
bugs with the label `Infra-Troopers`.

- [Trooper documentation (internal)](go/trooper)

## W3C

The World-Wide-Web Consortium. The original writers of the HTML and other
specifications. The [web-platform-tests](#web-platform-tests) are in a W3C
repository.

## web-platform-tests

A suite of about 25,000 tests that test various web platform specifications.

- [GitHub repository](https://github.com/w3c/web-platform-tests).

## WebKit

The rendering engine that powered Chrome until 2013 and currently powers Safari.

## WPT Exporter

Allows Chromium contributors to upstream their changes to
[web-platform-tests](#web-platform-tests) automatically.

- [Documentation](https://chromium.googlesource.com/chromium/src/+/master/docs/testing/web_platform_tests.md#Automatic-export-process)

## WPT Importer

Automatically synchronizes upstream changes from [web-platform-tests](#web-platform-tests)
into the Chromium source tree.

- [Documentation](https://chromium.googlesource.com/chromium/src/+/master/docs/testing/web_platform_tests.md#Automatic-import-process)
