package frontend

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"testing"

	"github.com/golang/protobuf/proto"
	"github.com/julienschmidt/httprouter"
	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/secrets/testsecrets"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/arquebus/app/backend"
	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/util"
)

func makeParams(items ...string) httprouter.Params {
	if len(items)%2 != 0 {
		return nil
	}
	params := make([]httprouter.Param, len(items)/2)
	for i := range params {
		params[i] = httprouter.Param{
			Key:   items[2*i],
			Value: items[2*i+1],
		}
	}
	return params
}

func testContext() context.Context {
	c := util.CreateTestContext()
	c = testsecrets.Use(c)
	c = templates.Use(
		c, prepareTemplates("../appengine/templates"), &templates.Extra{
			Request: &http.Request{
				URL: &url.URL{Path: "/assigner/test-assigner"},
			},
		},
	)
	c = auth.WithState(c, &authtest.FakeState{Identity: "valid_user@test.com"})
	datastore.GetTestable(c).AutoIndex(true)
	return c
}

// createAssigner creates a sample Assigner entity.
func createAssigner(c context.Context, id string) *model.Assigner {
	var cfg config.Assigner
	So(proto.UnmarshalText(util.SampleValidAssignerCfg, &cfg), ShouldBeNil)
	cfg.Id = id

	So(backend.UpdateAssigners(c, []*config.Assigner{&cfg}, "revision-1"), ShouldBeNil)
	datastore.GetTestable(c).CatchupIndexes()
	assigner, err := backend.GetAssigner(c, cfg.Id)
	So(assigner.ID, ShouldEqual, cfg.Id)
	So(err, ShouldBeNil)
	So(assigner, ShouldNotBeNil)

	return assigner
}

func createScheduledTask(c context.Context, assigner *model.Assigner) *model.Task {
	task := &model.Task{
		AssignerKey:   model.GenAssignerKey(c, assigner),
		Status:        model.TaskStatus_Scheduled,
		ExpectedStart: testclock.TestTimeUTC,
	}
	So(datastore.Put(c, task), ShouldBeNil)
	return task
}

func TestFrontend(t *testing.T) {
	t.Parallel()
	assignerID := "test-assigner"

	Convey("frontend", t, func() {
		w := httptest.NewRecorder()
		c := &router.Context{
			Context: testContext(),
			Writer:  w,
		}

		Convey("index", func() {
			indexPage(c)
			So(w.Code, ShouldEqual, 200)
		})

		Convey("assigner", func() {
			createAssigner(c.Context, assignerID)

			Convey("found", func() {
				c.Params = makeParams("AssignerID", assignerID)
				assignerPage(c)
				So(w.Code, ShouldEqual, 200)
			})

			Convey("not found, if assignerID not given", func() {
				assignerPage(c)
				So(w.Code, ShouldEqual, 404)
			})

			Convey("not found, if non-existing assignerID given", func() {
				c.Params = makeParams("AssignerID", "foo")
				assignerPage(c)
				So(w.Code, ShouldEqual, 404)
			})
		})

		Convey("task", func() {
			assigner := createAssigner(c.Context, assignerID)
			task := createScheduledTask(c.Context, assigner)

			Convey("found", func() {
				c.Params = makeParams(
					"AssignerID", assignerID,
					"TaskID", strconv.FormatInt(task.ID, 10),
				)
				taskPage(c)
				So(w.Code, ShouldEqual, 200)
			})

			Convey("not found, if no params given", func() {
				taskPage(c)
				So(w.Code, ShouldEqual, 404)
			})

			Convey("not found, if taskID not given", func() {
				c.Params = makeParams(
					"AssignerID", assignerID,
				)
				taskPage(c)
				So(w.Code, ShouldEqual, 404)
			})

			Convey("not found, if assignerID not given", func() {
				c.Params = makeParams(
					"TaskID", strconv.FormatInt(task.ID, 10),
				)
				taskPage(c)
				So(w.Code, ShouldEqual, 404)
			})

			Convey("not found, if non-existing taskID given", func() {
				c.Params = makeParams(
					"AssignerID", assignerID,
					"TaskID", strconv.FormatInt(task.ID+1, 10),
				)
				taskPage(c)
				So(w.Code, ShouldEqual, 404)
			})
		})
	})
}
