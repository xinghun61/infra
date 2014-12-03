# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from handlers import analyze_build_failure
from handlers import build_failure
from handlers import home
from handlers import list_build
from handlers import read_entity
from handlers import triage_analysis
from handlers import verify_analysis


handler_mappings = [
    ('/analyze-build-failure', analyze_build_failure.AnalyzeBuildFailure),
    ('/build-failure', build_failure.BuildFailure),
    ('/list-build', list_build.ListBuild),
    ('/read-entity', read_entity.ReadEntity),
    ('/triage-analysis', triage_analysis.TriageAnalysis),
    ('/verify-analysis', verify_analysis.VerifyAnalysis),
    ('/', home.Home),
]

application = webapp2.WSGIApplication(handler_mappings, debug=False)
