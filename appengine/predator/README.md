# Predator

[go/predator-site](https://sites.google.com/a/chromium.org/cr-culprit-finder/predator)

Predator is a culprit finder for Chrome crashes identified or reported on
Clusterfuzz, Fracas, and Cracas. Key features include:
* Suggest suspected CLs for a Chrome crash which has a regression range.
  * For crashes on Fracas and Cracas, we use metadata to infer the regression range.
* Suggest components for bug filing for all Chrome crashes.

Currently, the source code is public, but the AppEngine app is still internal.

Predator has a [dashboard](http://go/predator-dashboard) for the analysis result.

# Integration with other systems
* Predator is integrated with [Fracas](http://go/fracas) to publicly-reported Chrome crashes. Analysis results are reported back to Fracas and surface on Fracas UI for stability sheriffs.

* The old version of Predator (previously known as "Findit for Crashes") is integrated with [ClusterFuzz](https://cluster-fuzz.appspot.com) to analyze Chrome crashes identified by fuzzing in ClusterFuzz. There is on-going work to port the old version to here, and then Predator will run entirely on AppEngine & integrate with ClusterFuzz over the wire.

# Code structure

* [analysis](analysis): Core of analysis for Chrome crashes.
* [app](app): The App Engine modules to provide core services of Predator.
* [scripts](scripts): Utility scripts to run locally on developer's workstation.
* [first\_party](first_party): Libraries from sibling infra AppEngine app that Predator depends on, specifically including a few libs from [Findit](../findit).
* [third\_party](third_party): Third-party libraries that Predator depends on.

# Contributions

We welcome all contributions! Please refer to [DEV.md](DEV.md) for more info.
