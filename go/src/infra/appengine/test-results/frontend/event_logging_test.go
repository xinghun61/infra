package frontend

import (
	"testing"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"
	"golang.org/x/net/context"

	"infra/appengine/test-results/model"
	"infra/appengine/test-results/model/gen"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCreateEvent(t *testing.T) {
	var nilTime *float64
	pTrue := true

	Convey("create events", t, func() {
		ctx := context.Background()
		p := &UploadParams{
			TestType: "test_type",
			StepName: "step_name",
			Master:   "master",
			Builder:  "builder",
		}
		f := &model.FullResult{
			PathDelim:   proto.String("/"),
			BuildNumber: 42,
			BuildID:     12345,
			Tests: model.FullTest{
				"path": &model.FullTestLeaf{
					Actual:     []string{"PASS"},
					Expected:   []string{"PASS"},
					Runtime:    nilTime,
					Runtimes:   []*float64{nilTime, nilTime},
					Unexpected: &pTrue,
				},
				"other/path": &model.FullTestLeaf{
					Actual:   []string{"IMAGE+TEXT"},
					Expected: []string{"WONTFIX"},
				},
			},
		}

		zeroTS, err := ptypes.TimestampProto(time.Unix(int64(f.SecondsEpoch), 0))
		So(err, ShouldBeNil)
		So(zeroTS, ShouldNotBeNil)

		expected := []*gen.TestResultEvent{
			{
				Path:     "path",
				TestType: p.TestType,
				StepName: p.StepName,
				BuildbotInfo: &gen.BuildbotInfo{
					MasterName:  p.Master,
					BuilderName: p.Builder,
					BuildNumber: int64(f.BuildNumber),
				},
				BuildbucketInfo: &gen.BuildbucketInfo{
					BuildId: int64(f.BuildID),
				},
				StartTime: zeroTS,
				Run: &gen.TestRun{
					Actual:       []gen.ResultType{gen.ResultType_PASS},
					Expected:     []gen.ResultType{gen.ResultType_PASS},
					Name:         "path",
					IsUnexpected: true,
				},
				BuildId: "12345",
			},
			{
				Path:     "other/path",
				TestType: p.TestType,
				StepName: p.StepName,
				BuildbotInfo: &gen.BuildbotInfo{
					MasterName:  p.Master,
					BuilderName: p.Builder,
					BuildNumber: int64(f.BuildNumber),
				},
				BuildbucketInfo: &gen.BuildbucketInfo{
					BuildId: int64(f.BuildID),
				},
				StartTime: zeroTS,
				Run: &gen.TestRun{
					Actual:       []gen.ResultType{gen.ResultType_IMAGE_TEXT},
					Expected:     []gen.ResultType{gen.ResultType_WONTFIX},
					Name:         "other/path",
					IsUnexpected: false,
				},
				BuildId: "12345",
			},
		}

		evts, err := createTestResultEvents(ctx, f, p)
		So(err, ShouldBeNil)
		So(len(evts), ShouldEqual, 2)
		for _, evt := range evts {
			So(evt, ShouldBeIn, expected)
		}
	})
}
