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
			Tests: model.FullTest{
				"path": &model.FullTestLeaf{
					Actual:   []string{"PASS"},
					Expected: []string{"PASS"},
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
				StartTime: zeroTS,
				Run: &gen.TestRun{
					Actual:   []gen.ResultType{gen.ResultType_PASS},
					Expected: []gen.ResultType{gen.ResultType_PASS},
					Name:     "path",
				},
			},
		}
		evts, err := createTestResultEvents(ctx, f, p)
		So(err, ShouldBeNil)
		So(evts, ShouldResemble, expected)
	})

}
