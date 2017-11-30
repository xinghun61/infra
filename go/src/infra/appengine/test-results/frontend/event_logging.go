package frontend

import (
	"fmt"
	"time"

	"github.com/golang/protobuf/ptypes"
	"golang.org/x/net/context"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/test-results/model"
	"infra/appengine/test-results/model/gen"
	"infra/libs/eventupload"

	"cloud.google.com/go/bigquery"
)

const (
	bqTestResultsDataset = "events"
	bqTestResultsTable   = "test_results"
)

func sendEventsToBigQuery(c context.Context, tres []*gen.TestResultEvent) error {
	for _, tre := range tres {
		if tre.TestType == "" {
			return errors.Reason("TestResultEvent is missing required field").Err()
		}
	}
	client, err := bigquery.NewClient(c, info.AppID(c))
	if err != nil {
		return err
	}
	up := eventupload.NewUploader(c, client, bqTestResultsDataset, bqTestResultsTable)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true
	return up.Put(c, tres)
}

func createTestResultEvents(c context.Context, f *model.FullResult, p *UploadParams) ([]*gen.TestResultEvent, error) {
	var i bool
	if f.Interrupted != nil {
		i = *(f.Interrupted)
	}

	if f.PathDelim == nil {
		return nil, errors.Reason("FullResult must have PathDelim to flatten Tests").Err()
	}
	s := *(f.PathDelim)

	var tres []*gen.TestResultEvent
	for name, ftl := range f.Tests.Flatten(s) {
		actual, err := testResultTypes(ftl.Actual)
		if err != nil {
			return nil, err
		}
		expected, err := testResultTypes(ftl.Expected)
		if err != nil {
			return nil, err
		}

		testRun := &gen.TestRun{
			Actual:   actual,
			Expected: expected,
			Bugs:     ftl.Bugs,
			Name:     name,
		}

		startTime, err := ptypes.TimestampProto(time.Unix(int64(f.SecondsEpoch), 0))
		if err != nil {
			return nil, err
		}

		evt := &gen.TestResultEvent{
			BuildbotInfo: &gen.BuildbotInfo{
				MasterName:  p.Master,
				BuilderName: p.Builder,
				BuildNumber: int64(f.BuildNumber),
			},
			// TODO: plumb build_id all the way through the test results upload scripts.
			BuildId:     p.BuildID,
			Path:        name,
			TestType:    p.TestType,
			StepName:    p.StepName,
			Interrupted: i,
			StartTime:   startTime,
			Run:         testRun,
		}

		tres = append(tres, evt)
	}

	return tres, nil
}

func testResultType(t string) (gen.ResultType, error) {
	if ret, ok := gen.ResultType_value[t]; ok {
		return gen.ResultType(ret), nil
	}
	return 0, fmt.Errorf("Unknown ResultType: %v", t)
}

func testResultTypes(ts []string) ([]gen.ResultType, error) {
	ret := make([]gen.ResultType, len(ts))
	for i, t := range ts {
		var v gen.ResultType
		var err error
		if v, err = testResultType(t); err != nil {
			return nil, err
		}
		ret[i] = v
	}
	return ret, nil
}

func logTestResultEvents(c context.Context, f *model.FullResult, p *UploadParams) {
	tres, err := createTestResultEvents(c, f, p)
	if err != nil {
		logging.WithError(err).Errorf(c, "could not create TestResultEvents")
		return
	}
	err = sendEventsToBigQuery(c, tres)
	if err != nil {
		if pme, ok := err.(bigquery.PutMultiError); ok {
			logPutMultiError(c, pme)
		} else {
			logging.WithError(err).Errorf(c, "error sending event")
		}
	}
	return
}

func logPutMultiError(c context.Context, pme bigquery.PutMultiError) {
	for _, rie := range pme {
		for _, e := range rie.Errors {
			logging.WithError(e).Errorf(c, "error sending event to BigQuery")
		}
	}
}
