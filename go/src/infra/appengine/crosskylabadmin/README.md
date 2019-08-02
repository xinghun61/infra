#ChromeOS Skylab Admin

[TOC]

## Overview

Chrome OS Skylab Admin is a Google App Engine app (in Go) that supports the following:

### Manage Lab Device Inventory

Lab device inventory is broadly composed of the following:

 * Device hardware attributes - Static (immutable) hardware characteristics of lab devices
    * E.g. device model, SoC architecture, graphics chip family, bluetooth, etc...
 * Lab device configuration - Lab deployment details needed to communicate with, manage, and run tests on a specific device
    * E.g. hostname, servo port, servo host, etc...
 * Lab device state - Current status information about a given device
    * E.g. Scheduling availability, servo health, etc...

This service is responsible for managing and providing access to this config.

Currently, the config is backed by the Skylab inventory
[repo](https://chrome-internal.googlesource.com/chromeos/infra_internal/skylab_inventory/#)
and cached/served from
[Datastore](https://pantheon.corp.google.com/datastore/entities;kind=cachedInventoryDut;ns=__$DEFAULT$__/query/kind?project=chromeos-skylab-bot-fleet).

Updates to this config come from the following sources:

 * skylab command-line tool
    * Supports adding new lab devices and setting lab-specific details
    * Supports administrative updates/operations to lab devices
 * Lab device bots
    * Device bots dynamically detect hardware attributes and report them to this service
    * Device bots also report lab device status information

This config is then sourced/read by device bots to support the following:

 * Reported to swarming as schedulable attributes that will match test requests
 * Lab setup is used to communicate with the device and device peripherals

### Keep Devices Healthy

This service is trying to keep devices in a healthy, schedulable state at all
times.
Device health can degrade for many reasons (bad test, provisioning failure,
etc...) and this service supports recovering those devices with the following:

 * API to manually schedule device repair jobs (invoked via skylab tool)
 * Scheduling automated repair jobs for any devices it detects as unhealthy

### Other Admin Functions

This service is a bit of a catch-all and performs various other functions
required to keep the system healthy.

For example, here are some of the additional functions (not comprehensive):

 * Triggers balancing across critical device pools
 * Reports time-series metrics used for monitoring/analysis
 * Reports inventory to Drone Queen for drone/bot management


## Code/Development Setup

For initial setup, follow the [Chrome Infra Go procedures](https://chromium.googlesource.com/infra/infra/+/refs/heads/master/go/README.md)

For environment setup, follow the [Bootstrap
procedures](https://chromium.googlesource.com/infra/infra/+/refs/heads/master/go/README.md#Bootstrap)

## Application Environments

 * Production - [cloud project](https://pantheon.corp.google.com/home/dashboard?project=chromeos-skylab-bot-fleet)
 * Staging - [cloud project](https://pantheon.corp.google.com/home/dashboard?project=skylab-staging-bot-fleet)
 * Local - 'cd go/src/infra/appengine/crosskylabadmin && make dev'

## Test

 * Unit testing - 'cd go/src/infra/appengine/crosskylabadmin && make test'
 * Functional/integration testing - No automated testing

## Release Procedures

 * cd go/src/infra/appengine/crosskylabadmin
 * make up-staging && switch-staging (Staging)
 * make up-prod && switch-prod (Production)
