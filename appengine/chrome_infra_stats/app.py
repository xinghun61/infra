# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

import views  # pylint: disable=W0403


app = webapp2.WSGIApplication([
    ('/_ah/warmup', views.StartPage),
    ('/_ah/start', views.StartPage),
    ('/crawl_masters', views.CrawlMasters),
    ('/cache_page', views.CachePage),
    ('/cull_steps', views.CullOldSteps),
    ('/cache_steps', views.CacheSteps),
    ('/run_step_summary/(.+)/(.+)/(.+)', views.RunStepSummary),
    ('/run_step_summary/(.+)/(.+)', views.RunStepSummary),
    ('/run_step_summary/(.+)', views.RunStepSummary),
    ('/run_step_summary_jobs', views.RunStepSummaryJobs),
    ('/delete_summary/(.+)', views.DeleteStepSummary),
    ('/delete_all_summaries', views.DeleteAllStepSummaries),
    ('/masters', views.Masters),
    ('/view/(.+)/(.+)/(.+)', views.StepView),
    ('/view/(.+)/(.+)', views.StepView),
    ('/view/(.+)', views.StepView),
    ('/record/(.+)/(.+)', views.GetStepsForHour),
    ('/', views.MainPage),
])
