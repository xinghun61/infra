package frontend

import (
	"fmt"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"
	"golang.org/x/net/context"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/bq"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"

	"infra/appengine/test-results/model"
	"infra/appengine/test-results/model/gen"

	"cloud.google.com/go/bigquery"
)

const (
	bqTestResultsDataset = "events"
	bqTestResultsTable   = "test_results"
)

func sendEventsToBigQuery(c context.Context, tres []*gen.TestResultEvent) error {
	logging.Debugf(c, "start sendEventsToBigQuery")
	defer logging.Debugf(c, "end sendEventsToBigQuery")

	for _, tre := range tres {
		if tre.TestType == "" {
			return errors.Reason("TestResultEvent is missing required field").Err()
		}
	}
	client, err := bigquery.NewClient(c, info.AppID(c))
	if err != nil {
		return err
	}
	up := bq.NewUploader(c, client, bqTestResultsDataset, bqTestResultsTable)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true
	m := make([]proto.Message, len(tres))
	for i, t := range tres {
		m[i] = t
	}
	return up.Put(c, m...)
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

		if ftl.Unexpected != nil {
			testRun.IsUnexpected = *ftl.Unexpected
		}

		if ftl.Runtime != nil {
			testRun.Time = float32(*ftl.Runtime)
		}

		for _, t := range ftl.Runtimes {
			if t != nil {
				testRun.Times = append(testRun.Times, float32(*t))
			}
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
			Path:        name,
			TestType:    p.TestType,
			StepName:    p.StepName,
			Interrupted: i,
			StartTime:   startTime,
			Run:         testRun,
		}

		if f.BuildID != 0 {
			evt.BuildId = fmt.Sprintf("%d", f.BuildID)
			evt.BuildbucketInfo = &gen.BuildbucketInfo{
				BuildId: int64(f.BuildID),
			}
		}

		if f.ChromiumRev != nil {
			evt.ChromiumRevision = *f.ChromiumRev
		}

		tres = append(tres, evt)
	}

	return tres, nil
}

func testResultType(t string) (gen.ResultType, error) {
	if t == "IMAGE+TEXT" {
		return gen.ResultType_IMAGE_TEXT, nil
	}

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
	logging.Debugf(c, "start logTestResultEvents")
	defer logging.Debugf(c, "end logTestResultEvents")

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
