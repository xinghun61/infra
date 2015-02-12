# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""URL mappings for the codereview package."""

from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url
import django.views.defaults
from django.views.generic.base import RedirectView

from codereview import feeds

urlpatterns = patterns(
    'codereview.views',

    # TODO(ojan): Remove the scrape urls once there are JSON APIs for them.
    (r'^scrape/?$', 'index'),
    (r'^$', 'index'),

    (r'^scrape/(\d+)/?$', 'show', {}, 'show_bare_issue_number'),
    (r'^(\d+)/?$', 'show', {}, 'show_bare_issue_number'),

    # TODO(ojan): Use the api and remove the scrape URL.
    (r'^scrape/settings$', 'settings'),
    (r'^settings$', 'settings'),
    (r'^api/settings$', 'api_settings'),

    # TODO(ojan): Use the api and remove the scrape URL.
    (r'^scrape/user/([^/]+)$', 'show_user'),
    (r'^user/([^/]+)$', 'show_user'),
    (r'^api/user/([^/]+)$', 'api_show_user'),

    (r'^leaderboard/?$', RedirectView.as_view(url='/leaderboard/30')),
    (r'^leaderboard_json/(.+)$', 'leaderboard_json'),
    (r'^leaderboard/(.+)$', 'leaderboard'),
    (r'^user/(?P<user>[^/]+)/stats/?$',
     RedirectView.as_view(url='/user/%(user)s/stats/30')),
    (r'^user/([^/]+)/stats/([^/]+)$', 'show_user_stats'),
    (r'^user/([^/]+)/stats_json/([^/]+)$', 'show_user_stats_json'),

    # TODO(ojan): all/mine/starred/show are not useful. Remove them once
    # we remove the deprecated UI.
    (r'^all$', 'view_all'),
    (r'^mine$', 'mine'),
    (r'^api/mine$', 'api_mine'),
    (r'^starred$', 'starred'),
    (r'^(\d+)/(?:show)?$', 'show'),

    (r'^upload$', 'upload'),
    (r'^(\d+)/edit$', 'edit'),
    (r'^(\d+)/delete$', 'delete'),
    (r'^(\d+)/close$', 'close'),
    (r'^(\d+)/mail$', 'mailissue'),
    (r'^(\d+)/publish$', 'publish'),
    (r'^(\d+)/delete_drafts$', 'delete_drafts'),
    (r'^download/issue(\d+)_(\d+)\.diff', 'download'),
    (r'^download/issue(\d+)_(\d+)_(\d+)\.diff', 'download_patch'),
    (r'^(\d+)/patch/(\d+)/(\d+)$', 'patch'),
    (r'^(\d+)/image/(\d+)/(\d+)/(\d+)$', 'image'),
    (r'^(\d+)/diff/(\d+)/(.+)$', 'diff'),
    (r'^(\d+)/diff2/(\d+):(\d+)/(.+)$', 'diff2'),
    # The last path element is optional till the polymer UI supports it.
    (r'^(\d+)/diff_skipped_lines/(\d+)/(\d+)/(\d+)/(\d+)/([tba])/(\d+)$',
     'diff_skipped_lines'),
    (r'^(\d+)/diff_skipped_lines/(\d+)/(\d+)/(\d+)/(\d+)/([tba])/(\d+)/(\d+)$',
     'diff_skipped_lines'),
    (r'^(\d+)/diff_skipped_lines/(\d+)/(\d+)/$',
     django.views.defaults.page_not_found, {}, 'diff_skipped_lines_prefix'),
    # The last path element is optional till the polymer UI supports it.
    (r'^(\d+)/diff2_skipped_lines/(\d+):(\d+)/(\d+)/(\d+)/(\d+)/([tba])/(\d+)$',
     'diff2_skipped_lines'),
    (r'^(\d+)/diff2_skipped_lines/(\d+):(\d+)/(\d+)/(\d+)/(\d+)/([tba])'
     '/(\d+)/(\d+)$', 'diff2_skipped_lines'),
    (r'^(\d+)/diff2_skipped_lines/(\d+):(\d+)/(\d+)/$',
     django.views.defaults.page_not_found, {}, 'diff2_skipped_lines_prefix'),
    (r'^(\d+)/upload_content/(\d+)/(\d+)$', 'upload_content'),
    (r'^(\d+)/upload_patch/(\d+)$', 'upload_patch'),
    (r'^(\d+)/upload_complete/(\d+)?$', 'upload_complete'),
    (r'^(\d+)/description$', 'description'),
    (r'^(\d+)/fields', 'fields'),
    (r'^(\d+)/star$', 'star'),
    (r'^(\d+)/unstar$', 'unstar'),
    (r'^(\d+)/draft_message$', 'draft_message'),
    (r'^api/(\d+)/?$', 'api_issue'),
    (r'^api/tryservers/?$', 'api_tryservers'),
    (r'^api/(\d+)/(\d+)/?$', 'api_patchset'),
    (r'^api/(\d+)/(\d+)/draft_comments$', 'api_draft_comments'),
    (r'^tarball/(\d+)/(\d+)$', 'tarball'),
    (r'^inline_draft$', 'inline_draft'),
    (r'^account_delete$', 'account_delete'),
    (r'^migrate_entities$', 'migrate_entities'),
    (r'^user_popup/(.+)$', 'user_popup'),
    (r'^(\d+)/patchset/(\d+)$', 'patchset'),
    (r'^(\d+)/patchset/(\d+)/delete$', 'delete_patchset'),
    (r'^(\d+)/patchset/(\d+)/edit_patchset_title$', 'edit_patchset_title'),
    (r'^account$', 'account'),
    (r'^use_uploadpy$', 'use_uploadpy'),
    (r'^xsrf_token$', 'xsrf_token'),
    # patching upload.py on the fly
    (r'^static/upload.py$', 'customized_upload_py'),
    (r'^search$', 'search'),
    (r'^get-access-token$', 'get_access_token'),
    (r'^oauth2callback$', 'oauth2callback'),
    # Restricted access.
    (r'^restricted/cron/update_yesterday_stats$',
        'cron_update_yesterday_stats'),
    (r'^restricted/tasks/refresh_all_stats_score$',
        'task_refresh_all_stats_score'),
    (r'^restricted/tasks/update_stats$', 'task_update_stats'),
    (r'^restricted/update_stats$', 'update_stats'),
    (r'^restricted/set-client-id-and-secret$', 'set_client_id_and_secret'),
    (r'^restricted/tasks/calculate_delta$', 'task_calculate_delta'),
    (r'^restricted/tasks/migrate_entities$', 'task_migrate_entities'),
    (r'^restricted/user/([^/]+)/block$', 'block_user'),
    (r'^_ah/mail/(.*)', 'incoming_mail'),
    )


### XMPP notification support
urlpatterns += patterns(
  'codereview.notify_xmpp',
  (r'^_ah/xmpp/message/chat/', 'incoming_chat'),
)


### Revert patchset support
urlpatterns += patterns(
  'codereview.revert_patchset',
  (r'^api/(\d+)/(\d+)/revert$', 'revert_patchset'),
)


### RSS Feed support
urlpatterns += patterns(
    '',
    url(r'^rss/all$', feeds.AllFeed(), name='rss_all'),
    url(r'^rss/mine/(.*)$', feeds.MineFeed(), name='rss_mine'),
    url(r'^rss/reviews/(.*)$', feeds.ReviewsFeed(), name='rss_reviews'),
    url(r'^rss/closd/(.*)$', feeds.ClosedFeed(), name='rss_closed'),
    url(r'^rss/issue/(.*)$', feeds.OneIssueFeed(), name='rss_issue'),
)

# Chromium urls
urlpatterns += patterns(
    'codereview.views_chromium',
    (r'^(\d+)/edit_flags$', 'edit_flags'),
    (r'^(\d+)/binary/(\d+)/(\d+)/(\d+)$', 'download_binary'),
    (r'^(\d+)/try/(\d+)/?$', 'try_patchset'),
    (r'^conversions$', 'conversions'),
    (r'^status_listener$', 'status_listener'),
    (r'^get_pending_try_patchsets$', 'get_pending_try_patchsets'),
    (r'^restricted/update_default_builders$', 'update_default_builders'),
    (r'^restricted/update_tryservers$', 'update_tryservers'),
    (r'^restricted/delete_old_pending_jobs$', 'delete_old_pending_jobs'),
    (r'^restricted/delete_old_pending_jobs_task$',
      'delete_old_pending_jobs_task'),
    )
