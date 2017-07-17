# Predator

[Predator site](https://sites.google.com/a/chromium.org/cr-culprit-finder/predator)

Predator is a culprit finder for Chrome crashes identified or reported on
[ClusterFuzz](https://cluster-fuzz.appspot.com), [Fracas] and [Cracas]. Key features include:
* Suggest suspected CLs for a Chrome crash which has a regression range.
  * For crashes on Fracas and Cracas, we use metadata to infer the regression range.
* Suggest components for bug filing for all Chrome crashes.

Currently, the source code is public, but the AppEngine app is still internal.
# TODO(katesonia): Add links for Fracas and Cracas after moving to appspot.
Predator has 2 dashboards for Fracas and Cracas.

# Integration with other systems
* Predator is integrated with Fracas/Cracas to publicly-reported Chrome crashes. Analysis results are reported back to Fracas/Cracas and surface on Fracas/Cracas UI for stability sheriffs.

* The old version of Predator (previously known as "Findit for Crashes") is integrated with  to analyze Chrome crashes identified by fuzzing in ClusterFuzz. There is on-going work to port the old version to here, and then Predator will run entirely on AppEngine & integrate with ClusterFuzz over the wire.

# Code structure

* [analysis](analysis): Core of analysis for Chrome crashes.
* [app] (app): The App Engine modules to provide heuristic analysis of Predator.
* [scripts](scripts): Utility scripts to run locally on developer's workstation.
* [first\_party](first_party): Libraries from sibling infra AppEngine app that Predator depends on, specifically including a few libs from [Findit](../findit).
* [third\_party](third_party): Third-party libraries that Predator depends on.

# Contributions
We welcome all contributions! Please refer to [DEV.md](DEV.md) for more info.
