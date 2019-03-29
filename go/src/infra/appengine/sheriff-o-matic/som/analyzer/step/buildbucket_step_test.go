package step

import (
	"testing"

	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/test-results/model"

	"golang.org/x/net/context"

	bbpb "go.chromium.org/luci/buildbucket/proto"

	ptypesstruct "github.com/golang/protobuf/ptypes/struct"

	. "github.com/smartystreets/goconvey/convey"
)

func TestTestResultBuildBucketAnalyzer(t *testing.T) {
	ctx := context.Background()

	Convey("not a test step", t, func() {
		tr := &client.StubTestResults{}

		a := &testResultBuildBucketAnalyzer{tr, nil}
		res, err := a.Analyze(ctx, &bbpb.Step{
			Name: "this is not a test step. sorry.",
		}, nil)
		So(err, ShouldBeNil)
		So(res, ShouldBeEmpty)
	})

	Convey("is a test step", t, func() {
		t := true

		a := &testResultBuildBucketAnalyzer{
			&client.StubTestResults{
				FullResult: &model.FullResult{
					Tests: model.FullTest{
						"foo": &model.FullTestLeaf{
							Actual:     []string{"FAIL"},
							Unexpected: &t,
						},
					},
				},
			},
			&client.StubFindIt{},
		}

		res, err := a.Analyze(ctx, &bbpb.Step{
			Name: "browser_tests",
		}, &bbpb.Build{
			Input: &bbpb.Build_Input{
				Properties: &ptypesstruct.Struct{
					Fields: map[string]*ptypesstruct.Value{
						"mastername": {
							Kind: &ptypesstruct.Value_StringValue{
								StringValue: "asdasd",
							},
						},
						"buildername": {
							Kind: &ptypesstruct.Value_StringValue{
								StringValue: "asdasd",
							},
						},
					},
				},
			},
		})
		So(err, ShouldBeNil)
		So(res, ShouldNotBeEmpty)
		So(len(res), ShouldEqual, 1)
		So(res[0].Kind(), ShouldEqual, "test")
	})
}
