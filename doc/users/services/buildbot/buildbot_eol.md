# Buildbot End of Life

*If you maintain or own Buildbot masters and builders running on Chrome’s infrastructure, please read on. For all others, please see the user [FAQ](https://chromium.googlesource.com/chromium/src/+/master/docs/luci_migration_faq.md) for changes to your user experience.*

**March 1, 2019** is the end of life date for all Buildbot masters and builders running on Chromium/Chrome hosted on [chromium.org](https://www.chromium.org).

As of March 1, 2019, all Buildbot master processes and their corresponding builders running on Chrome Operations (historically Chrome Infra) infrastructure will be permanently shut down. All existing builders will have already been contacted to migrate their builders to [LUCI](../about_luci.md), our new continuous build integration system. This work is scheduled to be completed within the next few months.

### **What does this mean for Buildbot master/builder owners?**
All buildbot master processes will be shut down no later than **March 1, 2019**, when we will immediately begin decommissioning the physical master machines and bots.

If your Buildbot builder is not converted to LUCI on March 1, 2019, your builder will stop running.

Specifically, the following will occur on March 1, 2019:
* All buildbot masters, builders and bots will go offline
* Buildbot builds will no longer be triggered
* Troopers will no longer respond to any alerts or issues that arise from Buildbot builders
* Associated alerts for Buildbot masters/builders will be turned down
* [ci.chromium.org](https://ci.chromium.org) becomes the sole user interface serving LUCI builds
* [build.chromium.org](https://build.chromium.org) will stop serving any data/UI

We are targeting all builders slated for migration to LUCI to be completed prior to March 1.

### **Can I stay on Buildbot?**
**No.** To continue to run builds on Chrome’s infrastructure, you must transition to LUCI.

If you still choose to remain on Buildbot and do not wish to transition to LUCI, you **MUST** set up and run your own Buildbot instance prior to March 1, 2019. Please reach out to infra-dev@chromium.org if you decide to choose this option.

You will be responsible for completing the following prior to **February 28th, 2019**
* Fork the Chromium Buildbot build repo which contains the buildbot master and slave code.
* Acquire a machine to serve as your master machine.
 _This machine will run your Buildbot master processes (we recommend GCE)_
* Acquire machine(s) to serve as your Buildbot slave machines.
 _These machines will run your builds (we recommend GCE for these as well, where applicable)._
* Change the slaves.cfg information in your forked repo for your master(s) to refer to the new slave machines.
* Clone the build repo onto all your machines.
* Run the Buildbot master on the master machine.
 _‘make start’ in your master’s directory_
* Run the Buildbot slave process on the slave machine.
 _'make start’ in the slave’s clone of the build repo.
 Set up something like Puppet, Chef or Ansible to manage the statefulness of your machines._

**Congratulations!** You are now an owner of your own Buildbot setup. Please note that if you choose this option, Chrome Operations will **NOT** be supporting or maintaining your builds and machines. You will be the sole owner and maintainer of your Buildbot masters and builders.

### **I have questions!**
Check out our Chromium dev [FAQ](https://chromium.googlesource.com/chromium/src/+/master/docs/luci_migration_faq.md) to see if your question has already been answered. If you have other questions, please reach out to the Chrome Operations team at infra-dev@chromium.org.

We are looking forward to continuing to support your continuous integration and CQ/try bot needs solely on [LUCI](../about_luci.md) starting March 1, 2019.
