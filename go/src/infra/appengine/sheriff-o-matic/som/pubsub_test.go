package som

import (
	"bytes"
	"compress/zlib"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	testhelper "infra/monitoring/analyzer/test"
	client "infra/monitoring/client/test"
	"infra/monitoring/messages"

	"github.com/luci/gae/impl/dummy"
	"github.com/luci/gae/service/info"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

type giMock struct {
	info.RawInterface
	token  string
	expiry time.Time
	err    error
}

func (gi giMock) AccessToken(scopes ...string) (token string, expiry time.Time, err error) {
	return gi.token, gi.expiry, gi.err
}

func TestPostMiloPubSubHandler(t *testing.T) {
	Convey("bad push request", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		msg := "invalid json"
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(msg),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("bad message data", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		msg, err := json.Marshal(pushRequest{Message: pushMessage{Data: []byte("invalid data")}})
		So(err, ShouldBeNil)

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(string(msg)),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("bad message build extract", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		var b bytes.Buffer
		zw := zlib.NewWriter(&b)
		zw.Write([]byte("invalid build extract"))
		zw.Close()

		msg, err := json.Marshal(pushRequest{Message: pushMessage{Data: b.Bytes()}})
		So(err, ShouldBeNil)

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(string(msg)),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("good message empty build extract", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		bmm := buildMasterMsg{
			Master: &messages.BuildExtract{},
			Builds: []*messages.Build{},
		}
		bmmJSON, err := json.Marshal(bmm)
		So(err, ShouldBeNil)

		var b bytes.Buffer
		zw := zlib.NewWriter(&b)
		zw.Write(bmmJSON)
		zw.Close()

		msg, err := json.Marshal(pushRequest{Message: pushMessage{Data: b.Bytes()}})
		So(err, ShouldBeNil)

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(string(msg)),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("good message non-empty build extract", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", time.Now(), nil}
		})
		c = urlfetch.Set(c, &client.MockGitilesTransport{
			Responses: map[string]string{
				gkTreesURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"],
            "https://build.chromium.org/p/chromium.android": [
              "Android N5X Swarm Builder"
            ],
            "https://build.chromium.org/p/chromium.chrome": ["*"],
            "https://build.chromium.org/p/chromium.chromiumos": ["*"],
            "https://build.chromium.org/p/chromium.gpu": ["*"],
            "https://build.chromium.org/p/chromium.infra.cron": ["*"],
            "https://build.chromium.org/p/chromium.linux": ["*"],
            "https://build.chromium.org/p/chromium.mac": ["*"],
            "https://build.chromium.org/p/chromium.memory": ["*"],
            "https://build.chromium.org/p/chromium.webkit": ["*"],
            "https://build.chromium.org/p/chromium.win": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
				gkConfigURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,
				gkConfigInternalURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,
				gkTreesInternalURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
				gkTreesCorpURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
				gkConfigCorpURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,
			},
		})

		bf := testhelper.NewBuilderFaker("fake.master", "fake.builder")
		bf.Build(0).Step("steps").Results(0).BuildFaker.Step("compile").Results(0)

		bmm := buildMasterMsg{
			Master: &messages.BuildExtract{},
			Builds: bf.GetBuilds(),
		}
		bmmJSON, err := json.Marshal(bmm)
		So(err, ShouldBeNil)

		var b bytes.Buffer
		zw := zlib.NewWriter(&b)
		zw.Write(bmmJSON)
		zw.Close()

		msg, err := json.Marshal(pushRequest{Message: pushMessage{Data: b.Bytes()}})
		So(err, ShouldBeNil)

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(string(msg)),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})
}

func TestGetPubSubAlertsHandler(t *testing.T) {
	t.Parallel()
	Convey("main", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", time.Now(), nil}
		})

		c = urlfetch.Set(c, &client.MockGitilesTransport{
			Responses: map[string]string{
				gkTreesURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"],
            "https://build.chromium.org/p/chromium.android": [
              "Android N5X Swarm Builder"
            ],
            "https://build.chromium.org/p/chromium.chrome": ["*"],
            "https://build.chromium.org/p/chromium.chromiumos": ["*"],
            "https://build.chromium.org/p/chromium.gpu": ["*"],
            "https://build.chromium.org/p/chromium.infra.cron": ["*"],
            "https://build.chromium.org/p/chromium.linux": ["*"],
            "https://build.chromium.org/p/chromium.mac": ["*"],
            "https://build.chromium.org/p/chromium.memory": ["*"],
            "https://build.chromium.org/p/chromium.webkit": ["*"],
            "https://build.chromium.org/p/chromium.win": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
				gkTreesInternalURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
				gkTreesCorpURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
				gkConfigInternalURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,

				gkConfigURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,
				gkConfigCorpURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,
			},
		})

		getPubSubAlertsHandler(&router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("tree", "chromium"),
		})

		Printf("Body: %+v", string(w.Body.Bytes()))
		So(w.Code, ShouldEqual, 200)
	})

	Convey("error getting gatekeeper trees", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()
		c = urlfetch.Set(c, http.DefaultTransport)

		oldGetGKTrees := getGatekeeperTrees

		getGatekeeperTrees = func(c context.Context) (map[string]*messages.TreeMasterConfig, error) {
			return nil, fmt.Errorf("failure")
		}

		getPubSubAlertsHandler(&router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("tree", "chromium"),
		})

		getGatekeeperTrees = oldGetGKTrees
		So(w.Code, ShouldEqual, 500)
	})

	Convey("unrecognized gatekeeper tree", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()
		c = urlfetch.Set(c, http.DefaultTransport)

		oldGetGKTrees := getGatekeeperTrees

		getGatekeeperTrees = func(c context.Context) (map[string]*messages.TreeMasterConfig, error) {
			return map[string]*messages.TreeMasterConfig{"foo": nil}, nil
		}

		getPubSubAlertsHandler(&router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("tree", "chromium"),
		})

		getGatekeeperTrees = oldGetGKTrees
		So(w.Code, ShouldEqual, 404)
	})
}
