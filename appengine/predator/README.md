# Predator

[Predator site](https://sites.google.com/a/chromium.org/cr-culprit-finder/predator)

Predator is a culprit finder for Chrome crashes identified or reported on
[ClusterFuzz](https://cluster-fuzz.appspot.com), Fracas, Cracas and UMA Sampling Profiler. Key features include:
* Suggest suspected CLs for a Chrome crash which has a regression range.
  * For crashes on Fracas and Cracas, we use metadata to infer the regression range.
* Suggest components for bug filing for all Chrome crashes/regressions.

Predator has dashboards to monitor results for all clients:
Clusterfuzz (aarya@, mbarbella@): https://predator-for-me.appspot.com/clusterfuzz/dashboard
Fracas (jchinlee@): https://predator-for-me.appspot.com/fracas/dashboard
Cracas (ivanpe@): https://predator-for-me.appspot.com/cracas/dashboard
UMA Sampling Profiler (wittman@): https://predator-for-me.appspot.com/uma-sampling-profiler/dashboard

# Integration with other systems
* Predator is integrated with Fracas/Cracas to publicly-reported Chrome crashes. Analysis results are reported back to Fracas/Cracas and surface on Fracas/Cracas UI for stability sheriffs.

# Code structure

* [analysis](analysis): Core of analysis, this directory is not dependent on any
  infra or google app engine libraries.
  The predator.py is the entry point which we create changelist_classifier to
  find suspected cls, component_classifier to find suspected components and
  project_classifier to find suspected project.
* [app] (app): The App Engine modules to provide heuristic analysis of Predator.
* [scripts](scripts): Utility scripts to run locally on developer's workstation.
* [first\_party](first_party): Libraries from sibling infra AppEngine app that Predator depends on, specifically including a few libs from [Findit](../findit).
* [third\_party](third_party): Third-party libraries that Predator depends on.

# Contributions
We welcome all contributions! Please refer to [DEV.md](DEV.md) for more info.
