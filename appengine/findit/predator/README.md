# Code structure

* [analysis](analysis): Core library for analyzing Chrome crashes.
* [app](app): The App Engine app to provide web APIs to analyze Chrome crashes through invoking the core library above, and web pages to view & monitor analysis results.

# Refactoring guideline
* All core logic of analysis should live in [analysis](analysis), and it should
  be standalone, and not depend any App Engine APIs.
* All app-layer code should live in [app](app)
  * Frontend code rendering UIs to providing APIs for clients like ClusterFuzz/Fracas/Cracas should live in [app/frontend](app/frontend).
  * Backend code running the analysis should live in [app/backend](app/backend).
  * Shared code between the frontend and backend should live in [app/common](app/common).

# Next step
  When the refactoring is done, we will do a one-off move to appengine/predator.
