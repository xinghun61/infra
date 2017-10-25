const ACTIVITY_TABLE_REQUEST = 'ACTIVITY_TABLE_REQUEST'
const ACTIVITY_TABLE_RESPONSE_SUCCESS = 'ACITIVITY_TABLE_RESPONSE_SUCCESS'
const ACTIVITY_TABLE_RESPONSE_ERROR = 'ACTIVITY_TABLE_RESPONSE_ERROR'

const DAY_DETAILS_REQUEST = 'DAY_DETAILS_REQUEST'
const DAY_DETAILS_RESPONSE_SUCCESS = 'DAY_DETAILS_RESPONSE_SUCCESS'
const DAY_DETAILS_RESPONSE_ERROR = 'DAY_DETAILS_RESPONSE_ERROR'

const DUMMY_ACTIVITY_TABLE = {"Username":"benjhayden","Activities":[{"Changes":2,"Bugs":0,"Day":"2017-10-25T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-10-24T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-10-19T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-10-18T00:00:00Z"},{"Changes":2,"Bugs":1,"Day":"2017-10-16T00:00:00Z"},{"Changes":0,"Bugs":1,"Day":"2017-10-12T00:00:00Z"},{"Changes":6,"Bugs":0,"Day":"2017-10-11T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-10-10T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-10-09T00:00:00Z"},{"Changes":0,"Bugs":1,"Day":"2017-10-06T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-10-05T00:00:00Z"},{"Changes":1,"Bugs":2,"Day":"2017-10-04T00:00:00Z"},{"Changes":0,"Bugs":1,"Day":"2017-09-28T00:00:00Z"},{"Changes":0,"Bugs":2,"Day":"2017-09-27T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-09-19T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-09-18T00:00:00Z"},{"Changes":4,"Bugs":0,"Day":"2017-09-13T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-09-11T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-09-08T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-09-05T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-08-18T00:00:00Z"},{"Changes":1,"Bugs":1,"Day":"2017-08-17T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-08-15T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-08-14T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-08-10T00:00:00Z"},{"Changes":1,"Bugs":1,"Day":"2017-08-09T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-08-08T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-08-02T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-08-01T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-07-28T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-07-27T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-07-26T00:00:00Z"},{"Changes":2,"Bugs":1,"Day":"2017-07-25T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-07-24T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-07-21T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-07-20T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-07-19T00:00:00Z"},{"Changes":6,"Bugs":0,"Day":"2017-07-18T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-07-17T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-07-12T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-07-10T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-06-30T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-06-29T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-06-28T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-06-22T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-06-21T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-06-20T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-06-19T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-06-16T00:00:00Z"},{"Changes":3,"Bugs":1,"Day":"2017-06-15T00:00:00Z"},{"Changes":6,"Bugs":1,"Day":"2017-06-13T00:00:00Z"},{"Changes":5,"Bugs":0,"Day":"2017-06-12T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-06-09T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-06-08T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-06-07T00:00:00Z"},{"Changes":5,"Bugs":0,"Day":"2017-06-06T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-06-05T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-06-02T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-05-30T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-05-26T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-05-24T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-05-23T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-05-19T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-05-18T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-05-17T00:00:00Z"},{"Changes":0,"Bugs":1,"Day":"2017-05-12T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-05-09T00:00:00Z"},{"Changes":1,"Bugs":1,"Day":"2017-05-08T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-05-02T00:00:00Z"},{"Changes":4,"Bugs":0,"Day":"2017-05-01T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-04-28T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-04-25T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-04-21T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-04-20T00:00:00Z"},{"Changes":9,"Bugs":0,"Day":"2017-04-19T00:00:00Z"},{"Changes":6,"Bugs":0,"Day":"2017-04-17T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-04-14T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-04-10T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-04-06T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-04-03T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-03-28T00:00:00Z"},{"Changes":1,"Bugs":1,"Day":"2017-03-27T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-03-24T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-03-22T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-03-21T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2017-03-17T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-03-15T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-03-14T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-03-11T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-03-09T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-03-08T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-03-04T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-03-02T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-02-06T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-02-04T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-02-02T00:00:00Z"},{"Changes":5,"Bugs":0,"Day":"2017-02-01T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-01-30T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-01-25T00:00:00Z"},{"Changes":0,"Bugs":1,"Day":"2017-01-23T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-01-20T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-01-18T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-01-17T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-01-13T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-01-12T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2017-01-10T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2017-01-09T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-12-28T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-12-22T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2016-12-21T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-12-20T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-12-19T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-12-16T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-12-15T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2016-12-14T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-12-12T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-12-09T00:00:00Z"},{"Changes":4,"Bugs":0,"Day":"2016-12-08T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-12-07T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-12-02T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-12-01T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2016-11-30T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2016-11-29T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-11-28T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-11-23T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-11-22T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-11-16T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-11-15T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-11-09T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-11-01T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-10-27T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2016-10-20T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-10-19T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-10-17T00:00:00Z"},{"Changes":3,"Bugs":0,"Day":"2016-10-13T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-10-12T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-10-07T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-10-06T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-10-04T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-10-03T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-09-30T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-09-22T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-09-21T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-09-20T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-09-19T00:00:00Z"},{"Changes":4,"Bugs":0,"Day":"2016-09-16T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-09-15T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-09-14T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-09-13T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-09-12T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-09-09T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-09-08T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-09-02T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-09-01T00:00:00Z"},{"Changes":4,"Bugs":0,"Day":"2016-08-31T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-08-27T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-08-26T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-08-24T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-08-16T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-08-12T00:00:00Z"},{"Changes":1,"Bugs":0,"Day":"2016-08-09T00:00:00Z"},{"Changes":2,"Bugs":0,"Day":"2016-08-04T00:00:00Z"}]};

const DUMMY_DETAILS = {"Username":"benjhayden","Day":"2017-10-18T00:00:00Z","Bugs":[{"author":{"name":"seanmccullough@chromium.org"},"id":774285,"components":["Infra\u003eFlakiness"],"labels":["Type-Bug","Pri-3"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Available","summary":"standardize test results parsing/structs (plz can has protos?)","updated":"2017-10-12T22:47:49"},{"author":{"name":"katthomas@google.com"},"cc":[{"name":"martiniss@chromium.org"},{"name":"katthomas@chromium.org"},{"name":"zhangtiff@chromium.org"}],"id":772134,"components":["Infra\u003eFlakiness"],"labels":["Restrict-View-Google","Type-Bug","Pri-3"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Started","summary":"Merge errors on test-results","updated":"2017-10-16T22:55:43"},{"author":{"name":"seanmccullough@chromium.org"},"cc":[{"name":"ehmaldonado@chromium.org"},{"name":"stgao@chromium.org"}],"id":771758,"components":["Infra\u003eFlakiness"],"labels":["Restrict-View-Google","Infra-Troopers"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Assigned","summary":"Why did chromium-try-flakes stop reporting to FindIt in early August?","updated":"2017-10-04T22:12:40"},{"author":{"name":"ashleymarie@chromium.org"},"cc":[{"name":"perezju@chromium.org"},{"name":"hinoka@chromium.org"},{"name":"nednguyen@chromium.org"},{"name":"stgao@chromium.org"},{"name":"ashleymarie@chromium.org"}],"id":754825,"components":["Tests\u003eTelemetry"],"labels":["Type-Bug","Pri-2"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Assigned","summary":"PASS PASS PASS PASS appears flaky","updated":"2017-09-27T08:25:51"},{"author":{"name":"ojan@chromium.org"},"cc":[{"name":"seanmccullough@chromium.org"},{"name":"zhangtiff@chromium.org"}],"id":747438,"components":["Infra\u003eSheriffing\u003eSheriffOMatic"],"labels":["Pri-2","Milestone-Workflow"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Started","summary":"can't get to old builds of official builders","updated":"2017-08-09T18:09:07"},{"author":{"name":"seanmccullough@chromium.org"},"cc":[{"name":"sergiyb@chromium.org"},{"name":"jparent@chromium.org"},{"name":"zhangtiff@chromium.org"}],"id":732950,"components":["Infra\u003eSheriffing\u003eSheriffOMatic"],"labels":["Pri-2","Milestone-Flakiness"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Assigned","summary":"Port important Flakiness Dashboard features","updated":"2017-06-13T20:45:47"},{"author":{"name":"tandrii@chromium.org"},"cc":[{"name":"seanmccullough@chromium.org"},{"name":"zhangtiff@chromium.org"}],"id":721501,"components":["Infra\u003eSheriffing\u003eSheriffOMatic"],"labels":["Restrict-View-Google","Pri-2","Milestone-Reliability"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Started","summary":"Remove flaky tests from Sheriff-o-Matic Go tests","updated":"2017-09-27T19:00:04"},{"author":{"name":"dnj@chromium.org"},"id":718966,"components":["Infra\u003eSheriffing\u003eSheriffOMatic"],"labels":["Type-Bug","Pri-3","Milestone-Reliability"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Untriaged","summary":"Update \"Node.js\" pin to 6.10.3","updated":"2017-05-08T21:00:12"},{"author":{"name":"stgao@chromium.org"},"cc":[{"name":"seanmccullough@chromium.org"},{"name":"zhangtiff@chromium.org"}],"id":704974,"components":["Infra\u003eSheriffing\u003eGatekeeper"],"labels":["Pri-1","Type-Bug"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Assigned","summary":"Broken links for closures in tree status apps","updated":"2017-05-12T09:19:10"},{"author":{"name":"petermayo@google.com"},"cc":[{"name":"seanmccullough@chromium.org"},{"name":"martiniss@chromium.org"},{"name":"zhangtiff@chromium.org"}],"id":699553,"components":["Infra\u003eSheriffing\u003eSheriffOMatic"],"labels":["Pri-2","Hotlist-Google","Infra-DX","Milestone-UX"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Assigned","summary":"Stale sherrif-o-matic data unactionable","updated":"2017-07-25T15:08:04"},{"author":{"name":"seanmccullough@chromium.org"},"cc":[{"name":"seanmccullough@chromium.org"},{"name":"dnj@chromium.org"},{"name":"martiniss@chromium.org"},{"name":"zhangtiff@chromium.org"}],"id":682889,"components":["Infra\u003eSheriffing\u003eSheriffOMatic"],"labels":["Pri-2","Milestone-Milo"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Started","summary":"read build logs from logdog instead of buildbot","updated":"2017-01-23T22:21:04"},{"author":{"name":"sashab@chromium.org"},"cc":[{"name":"jparent@chromium.org"},{"name":"hinoka@chromium.org"},{"name":"benhenry@chromium.org"},{"name":"mikelawther@chromium.org"},{"name":"katthomas@chromium.org"},{"name":"estaab@chromium.org"},{"name":"zhangtiff@chromium.org"}],"id":637628,"components":["Infra\u003eDocumentation","Infra\u003eSheriffing"],"labels":["Pri-1","Type-Bug"],"owner":{"name":"seanmccullough@chromium.org"},"status":"Assigned","summary":"No sheriffs listed on waterfall on MTV weekend (non-APAC weekend)","updated":"2017-10-04T22:54:07"}],"Changes":[{"id":"infra%2Finfra~master~I25731ecb1d4181e29a599b9f8011126bd36b454d","project":"infra/infra","branch":"master","change_id":"I25731ecb1d4181e29a599b9f8011126bd36b454d","subject":"[who] fix some trailing semicolons that casued js errors","status":"MERGED","created":"2017-10-25 14:53:59.000000000","updated":"2017-10-25 15:41:21.000000000","submitted":"2017-10-25 15:41:21.000000000","insertions":4,"deletions":4,"_number":738213,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~Ifbcd1818e843f40a122fbf7f1ae904ce70eb9243","project":"infra/infra","branch":"master","change_id":"Ifbcd1818e843f40a122fbf7f1ae904ce70eb9243","subject":"[who] update bower for paper-item etc","status":"MERGED","created":"2017-10-25 15:13:10.000000000","updated":"2017-10-25 15:35:11.000000000","submitted":"2017-10-25 15:35:11.000000000","insertions":7,"deletions":1,"_number":738218,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~Id59fecda164577f735a224e40499f09f845ede68","project":"infra/infra","branch":"master","change_id":"Id59fecda164577f735a224e40499f09f845ede68","subject":"[who] fix relative paths for html imports","status":"MERGED","created":"2017-10-25 14:40:33.000000000","updated":"2017-10-25 15:30:01.000000000","submitted":"2017-10-25 15:30:01.000000000","insertions":8,"deletions":3,"_number":738212,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~I2d6f21a416c667c7f05f5401edc780768f55c1cd","project":"infra/infra","branch":"master","change_id":"I2d6f21a416c667c7f05f5401edc780768f55c1cd","subject":"[who] fix malformed bower.json","status":"MERGED","created":"2017-10-25 04:59:03.000000000","updated":"2017-10-25 14:41:20.000000000","submitted":"2017-10-25 14:41:20.000000000","insertions":1,"deletions":1,"_number":737529,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~I555ee1343f82c048237126e7dac98c99a4a58966","project":"infra/infra","branch":"master","change_id":"I555ee1343f82c048237126e7dac98c99a4a58966","subject":"[who] get real activity counts by day, from monorail and gerrit","status":"MERGED","created":"2017-10-25 03:37:31.000000000","updated":"2017-10-25 03:52:56.000000000","submitted":"2017-10-25 03:52:56.000000000","insertions":169,"deletions":7,"_number":737279,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~Ic6857d27dbbc10ef06aad49b2281f49850441391","project":"infra/infra","branch":"master","change_id":"Ic6857d27dbbc10ef06aad49b2281f49850441391","subject":"[who] Add dummy API calls for /_/history and /_/detail","status":"MERGED","created":"2017-10-25 00:54:59.000000000","updated":"2017-10-25 03:10:58.000000000","submitted":"2017-10-25 03:10:58.000000000","insertions":80,"deletions":1,"_number":736717,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~Ibc9487bb42d581ef329632894dab96d29377937c","project":"infra/infra","branch":"master","change_id":"Ibc9487bb42d581ef329632894dab96d29377937c","subject":"[who] Add auth stuff","status":"MERGED","created":"2017-10-25 00:13:54.000000000","updated":"2017-10-25 00:44:32.000000000","submitted":"2017-10-25 00:44:32.000000000","insertions":125,"deletions":1,"_number":736688,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~Ibccc1a3b5d8b53aa48fae844e176ee68b3d18cf3","project":"infra/infra","branch":"master","change_id":"Ibccc1a3b5d8b53aa48fae844e176ee68b3d18cf3","subject":"[who] bower stuff","status":"MERGED","created":"2017-10-24 22:37:17.000000000","updated":"2017-10-24 23:06:51.000000000","submitted":"2017-10-24 23:06:51.000000000","insertions":8,"deletions":1,"_number":736670,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~Iecab1b49836b5a6b3686aa420b7ab7b55c030e66","project":"infra/infra","branch":"master","change_id":"Iecab1b49836b5a6b3686aa420b7ab7b55c030e66","subject":"[who] initial dir","status":"MERGED","created":"2017-10-24 21:47:48.000000000","updated":"2017-10-24 22:32:01.000000000","submitted":"2017-10-24 22:32:01.000000000","insertions":604,"deletions":0,"_number":736433,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~I7500d3113c902eb2f241f695be095ec0b3dbf65d","project":"infra/infra","branch":"master","change_id":"I7500d3113c902eb2f241f695be095ec0b3dbf65d","subject":"[test-results] define a proto message to eventually replace json.","status":"NEW","created":"2017-10-17 00:45:51.000000000","updated":"2017-10-19 23:28:56.000000000","mergeable":true,"insertions":680,"deletions":0,"_number":722285,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~I219192bccae99d9fac181bb294f299881cc00132","project":"infra/infra","branch":"master","change_id":"I219192bccae99d9fac181bb294f299881cc00132","subject":"[som] update RELNOTES.md for weekly release","status":"MERGED","created":"2017-10-18 14:08:24.000000000","updated":"2017-10-18 17:40:41.000000000","submitted":"2017-10-18 17:40:41.000000000","insertions":11,"deletions":0,"_number":725861,"owner":{"_account_id":1121710}},{"id":"infra%2Finfra~master~Ibac0f42aa239981601fb8fbf828d77bf42b2faf1","project":"infra/infra","branch":"master","change_id":"Ibac0f42aa239981601fb8fbf828d77bf42b2faf1","subject":"[bqschema] add support for protos-as-tabledefs using Options","status":"NEW","created":"2017-10-17 21:40:32.000000000","updated":"2017-10-18 16:00:43.000000000","mergeable":true,"insertions":567,"deletions":30,"_number":724200,"owner":{"_account_id":1121710}}]};


const DEFAULT_STATE = {
  // The current selected username
  username: undefined,

  // The current selected day
  day: undefined,

  isFetchingActivityTable: false,
  activityTableError: undefined,
  // username -> Map(day -> guid)
  activityTables: {},

  isFetchingDayDetail: false,
  dayDetailError: undefined,
  // guid -> Object{clsCommitted, bugsOpened, bugsUpdated, bugsClosed}
  dayDetails: {},
};

function reduxAjax({path, body, requestType, successType, errorType, dispatch}) {
  if (false) {
    fetch(path, {
      method: 'POST',
      body: JSON.stringify(body),
    }).then(response => {
      dispatch({
        type: successType,
        response,
      });
    }).catch(error => {
      dispatch({
        type: errorType,
        error,
      });
    });
  } else {
    let response;
    if (successType === ACTIVITY_TABLE_RESPONSE_SUCCESS) {
      response = DUMMY_ACTIVITY_TABLE;
    } else if (successType === DAY_DETAILS_RESPONSE_SUCCESS) {
      response = DUMMY_DETAILS;
    }
    console.log(successType, response);
    setTimeout(() => {
      dispatch({
        type: successType,
        response,
      });
    }, 500);
  }

  return Object.assign({}, body, {type: requestType});
}

function activityTableRequest(state, action) {
  return Object.assign({}, state, {
    username: action.username,
    isFetchingActivityTable: true,
  });
}

function transformActivities(input) {
  var weeks = {};

  for (var i = 0; i < input.length; i++) {
    var item = input[i];
    var topOfWeek = new Date(item.Day);
    topOfWeek.setDate(topOfWeek.getDate() - topOfWeek.getDay());

    if ( !weeks.hasOwnProperty(topOfWeek.toString()) ) {
      weeks[topOfWeek.toString()] = [];
      // Populate with dummy date so there is 7 items in each array.
      for (var j = 0; j < 7; j++) {
        var newDate = new Date(topOfWeek);
        newDate.setDate(newDate.getDate() + j);
        weeks[topOfWeek.toString()].push({'Day': newDate.toString(), 'Changes': 0, 'Bugs': 0});
      }
    }

    // Actually populate with the real data.
    for (var j = 0; j < 7; j++) {
      var dummyItem = weeks[topOfWeek.toString()][j];
      var dummyDate = new Date(dummyItem.Day);
      var itemDate = new Date(item.Day);
      if (dummyDate.getTime() === itemDate.getTime()) {
        weeks[topOfWeek.toString()][j] = item;
      }
    }

    weeks[topOfWeek.toString()]
  }

  return weeks;
}

function activityTableResponseSuccess(state, action) {
  const activityTables = {};
  if (action.response) {
    var weeklyActivities = transformActivities(action.response.Activities);
    activityTables[action.response.Username] = weeklyActivities;
  }
  return Object.assign({}, state, {
    isFetchingActivityTable: false,
    activityTableError: undefined,
    activityTables: Object.assign(
      {}, state.activityTables, activityTables),
  });
}

function activityTableResponseError(state, action) {
  return Object.assign({}, state, {
    isFetchingActivityTable: false,
    activityTableError: action.error,
  });
}

function dayDetailsRequest(state, action) {
  return Object.assign({}, state, {
    day: action.day,
    isFetchingDayDetail: true,
  });
}

function dayDetailsResponseSuccess(state, action) {
  const dayDetails = {};
  const key = action.response.Username + ' ' + action.response.Day;
  dayDetails[key] = {
    Bugs: action.response.Bugs,
    Changes: action.response.Changes,
  };
  return Object.assign({}, state, {
    isFetchingDayDetail: false,
    dayDetailError: undefined,
    dayDetails: Object.assign(
      {}, state.dayDetails, dayDetails),
  });
}

function dayDetailsResponseError(state, action) {
  return Object.assign({}, state, {
    isFetchingDayDetail: false,
    dayDetailError: action.error,
  });
}

function rootReducer(state, action) {
  if (state === undefined) return DEFAULT_ACTION;
  switch (action.type) {
    case ACTIVITY_TABLE_REQUEST:
      return activityTableRequest(state, action);
    case ACTIVITY_TABLE_RESPONSE_SUCCESS:
      return activityTableResponseSuccess(state, action);
    case ACTIVITY_TABLE_RESPONSE_ERROR:
      return activityTableResponseError(state, action);
    case DAY_DETAILS_REQUEST:
      return dayDetailsRequest(state, action);
    case DAY_DETAILS_RESPONSE_SUCCESS:
      return dayDetailsResponseSuccess(state, action);
    case DAY_DETAILS_RESPONSE_ERROR:
      return dayDetailsResponseError(state, action);
    default:
      return state;
  }
}
