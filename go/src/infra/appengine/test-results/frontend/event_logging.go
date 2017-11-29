package frontend

import (
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/golang/protobuf/ptypes"
	"golang.org/x/net/context"

	"google.golang.org/api/iterator"
	"google.golang.org/appengine"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"

	"infra/appengine/test-results/model"
	"infra/appengine/test-results/model/gen"
	"infra/libs/eventupload"

	"cloud.google.com/go/bigquery"
)

const (
	bqTestResultsDataset = "events"
	//bqTestResultsTable     = "test_results"
	bqTestResultsWideTable = "test_results_wide"
	bqTestResultsTallTable = "test_results_tall"
)

// The "wide" approach.
func sendEventToBigQuery(c context.Context, tre *gen.TestResultEvent) error {
	if tre.TestType == "" {
		return errors.Reason("TestResultEvent is missing required field").Err()
	}
	client, err := bigquery.NewClient(c, info.AppID(c))
	if err != nil {
		return err
	}
	up := eventupload.NewUploader(c, client, bqTestResultsDataset, bqTestResultsWideTable)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true
	return up.Put(c, tre)
}

// Wide approach: write one row, many repeated values. One for each test run. Wider, shorter table.
func createTestResultEvent(c context.Context, f *model.FullResult, p *UploadParams) (*gen.TestResultEvent, error) {
	var i bool
	if f.Interrupted != nil {
		i = *(f.Interrupted)
	}

	// Use the default separator as specified here:
	// https://chromium.googlesource.com/chromium/src/+/master/docs/testing/json_test_results_format.md
	s := "/"
	if f.PathDelim != nil {
		s = *(f.PathDelim)
	}

	var tests []*gen.TestRun
	for name, ftl := range f.Tests.Flatten(s) {
		actual, err := testResultTypes(ftl.Actual)
		if err != nil {
			return nil, err
		}
		expected, err := testResultTypes(ftl.Expected)
		if err != nil {
			return nil, err
		}

		tests = append(tests, &gen.TestRun{
			Actual:   actual,
			Expected: expected,
			Bugs:     ftl.Bugs,
			Name:     name,
		})
	}

	startTime, err := ptypes.TimestampProto(time.Unix(int64(f.SecondsEpoch), 0))
	if err != nil {
		return nil, err
	}

	writeTime := ptypes.TimestampNow()
	return &gen.TestResultEvent{
		// TODO: plumb build_id all the way through the test result uploader recipe step?
		BuildId:     p.BuildID,
		TestType:    p.TestType,
		StepName:    p.StepName,
		Interrupted: i,
		StartTime:   startTime,
		Run:         &gen.TestRun{}, // eventuploader reflection logic will fail if .Run is nil.
		Runs:        tests,
		BuildbotInfo: &gen.TestResultEvent_BuildbotInfo{
			MasterName:  p.Master,
			BuilderName: p.Builder,
			BuildNumber: int64(f.BuildNumber),
		},
		WriteTime: writeTime,
	}, nil
}

// The "tall" approach.
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
	up := eventupload.NewUploader(c, client, bqTestResultsDataset, bqTestResultsTallTable)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true
	return up.Put(c, tres)
}

// Tall approach: One row per test run, no repeated run values. Longer, thinner table.
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
	writeTime := ptypes.TimestampNow()
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
			BuildbotInfo: &gen.TestResultEvent_BuildbotInfo{
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
			Runs:        []*gen.TestRun{},
			WriteTime:   writeTime,
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
	tre, err := createTestResultEvent(c, f, p)
	if err != nil {
		logging.WithError(err).Errorf(c, "could not create TestResultEvent")
		return
	}
	tres, err := createTestResultEvents(c, f, p)
	if err != nil {
		logging.WithError(err).Errorf(c, "could not create TestResultEvents")
		return
	}
	eventErrs := []error{}
	// We're writing both just to compare the output sizes and insert latencies.
	eventErrs = append(eventErrs, sendEventToBigQuery(c, tre))
	eventErrs = append(eventErrs, sendEventsToBigQuery(c, tres))
	for _, err := range eventErrs {
		if err != nil {
			if pme, ok := err.(bigquery.PutMultiError); ok {
				logPutMultiError(c, pme)
			} else {
				logging.WithError(err).Errorf(c, "error sending event")
			}
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

// BQ insert latency tracking: Everything below here can be removed after
// we determine which approach (tall vs wide) has lower latency.

// Should be called as a cron job at regular intervals.
func updateWriteAgeMetrics(ctx *router.Context) {
	ct, w, r := ctx.Context, ctx.Writer, ctx.Request

	c := appengine.WithContext(ct, r)
	appID := info.AppID(c)
	// Query BQ for latest write times
	client, err := bigquery.NewClient(c, appID)
	if err != nil {
		logging.WithError(err).Errorf(c, "UpdateWriteAgeMetrics: %+v", err)
		http.Error(w, fmt.Sprintf("error getting bigquery client: %v", err), http.StatusInternalServerError)
	}

	type Result struct {
		LatestWrite     time.Time
		Master, Builder string
		BuildNumber     int64
	}

	latestWriteQ := func(tableName string) (*Result, error) {
		q := client.Query(fmt.Sprintf(`
			SELECT MAX(write_time) AS LatestWrite,
				buildbot_info.master_name AS Master,
				buildbot_info.builder_name AS Builder,
				buildbot_info.build_number AS BuildNumber
			FROM [%s:events.%s]
			GROUP BY 2,3,4 ORDER BY 1 DESC LIMIT 1`, appID, tableName))
		it, err := q.Read(c)
		if err != nil {
			return nil, err
		}
		var r Result
		err = it.Next(&r)
		if err != nil && err != iterator.Done {
			return nil, err
		}

		return &r, nil
	}

	// Update write_latency table.
	for _, tableName := range []string{"test_results_tall", "test_results_wide"} {
		lw, err := latestWriteQ(tableName)
		if err != nil {
			logging.WithError(err).Errorf(c, "UpdateWriteAgeMetrics: %+v", err)
			http.Error(w, "error updating metrics", http.StatusInternalServerError)
			return
		}

		latency := time.Now().Sub(lw.LatestWrite)
		wl := &gen.WriteLatency{
			Master:       lw.Master,
			Builder:      lw.Builder,
			BuildNumber:  lw.BuildNumber,
			WriteLatency: int64(latency.Seconds()),
			TableName:    tableName,
		}
		up := eventupload.NewUploader(c, client, bqTestResultsDataset, "write_latency")
		up.SkipInvalidRows = true
		up.IgnoreUnknownValues = true
		if err := up.Put(c, wl); err != nil {
			logging.WithError(err).Errorf(c, "UpdateWriteAgeMetrics: %+v", err)
		}
	}

	io.WriteString(w, "OK")
}
