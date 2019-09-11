// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package eventlog

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"cloud.google.com/go/bigquery"
	"github.com/google/uuid"
	"golang.org/x/time/rate"
	bqapi "google.golang.org/api/bigquery/v2"
	"google.golang.org/api/googleapi"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"
	"go.chromium.org/luci/common/sync/dispatcher"
	"go.chromium.org/luci/common/sync/dispatcher/buffer"
	"go.chromium.org/luci/server/auth"
)

// RAMBufferedBQInserter implements AsyncBqInserter via in-RAM buffering of events
// for later sending to BQ.
type RAMBufferedBQInserter struct {
	ProjectID string
	DatasetID string
	TableID   string

	// channel does the heavy lifting for us:
	//  * buffering,
	//  * back-pressure,
	//  * ratelimiting,
	//  * retries,
	// allowing RAMBufferedBQInserter to focus on sending the data.
	channel dispatcher.Channel

	// insertRPCMock is used by tests to mock actual BQ insert API call.
	insertRPCMock func(context.Context, *bqapi.TableDataInsertAllRequest) (*bqapi.TableDataInsertAllResponse, error)
}

// NewRAMBufferedBQInserter instantiates new RAMBufferedBQInserter.
func NewRAMBufferedBQInserter(ctx context.Context, projectID, datasetID, tableID string) (r *RAMBufferedBQInserter, err error) {
	r = &RAMBufferedBQInserter{
		ProjectID: projectID,
		DatasetID: datasetID,
		TableID:   tableID,
	}
	r.channel, err = dispatcher.NewChannel(
		ctx,
		&dispatcher.Options{
			QPSLimit: rate.NewLimiter(
				10, // QPS
				15, // Burst
			),
			Buffer: buffer.Options{
				MaxLeases: 10,
				BatchSize: 100, // 100 BQ rows sent at once.
				FullBehavior: &buffer.DropOldestBatch{
					MaxLiveItems: 1000, // At most these many items not yet currently leased for sending.
				},
				Retry: func() retry.Iterator {
					return &retry.ExponentialBackoff{
						Limited: retry.Limited{
							Delay:    50 * time.Millisecond,
							Retries:  50,
							MaxTotal: 45 * time.Second,
						},
						Multiplier: 2,
					}
				},
			},
		},
		func(batch *buffer.Batch) error { return r.send(ctx, batch) },
	)
	return
}

// Insert implements AsyncBqInserter interface.
func (r *RAMBufferedBQInserter) Insert(ctx context.Context, rows ...bigquery.ValueSaver) error {
	insertName := uuid.New()
	for i, row := range rows {
		rowMap, insertID, err := row.Save()
		if err != nil {
			return errors.Annotate(err, "failed to get row map from %s", row).Err()
		}
		if insertID == "" {
			insertID = fmt.Sprintf("bqram:%s:%d", insertName, i)
		}
		rowJSON, err := valuesToJSON(rowMap)
		if err != nil {
			return errors.Annotate(err, "failed to JSON-serialize BQ row %s", row).Err()
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case r.channel.C <- &bqapi.TableDataInsertAllRequestRows{InsertId: insertID, Json: rowJSON}:
		}
	}
	return nil
}

// CloseAndDrain stops accepting new rows and waits until all buffered rows are
// sent or provided `ctx` times out.
func (r *RAMBufferedBQInserter) CloseAndDrain(ctx context.Context) {
	r.channel.CloseAndDrain(ctx)
}

func (r *RAMBufferedBQInserter) send(ctx context.Context, batch *buffer.Batch) error {
	rows := make([]*bqapi.TableDataInsertAllRequestRows, 0, len(batch.Data))
	for _, d := range batch.Data {
		rows = append(rows, d.(*bqapi.TableDataInsertAllRequestRows)) // despite '...Rows', it's just 1 row.
	}
	ctx = logging.SetField(ctx, "rows", len(rows))
	ctx = logging.SetField(ctx, "first-iid", rows[0].InsertId)

	logging.Infof(ctx, "Sending to BigQuery")
	f := r.insertRPC
	if r.insertRPCMock != nil {
		f = r.insertRPCMock
	}
	// NOTE: dispatcher.Channel retries for us if error is transient.
	resp, err := f(ctx, &bqapi.TableDataInsertAllRequest{
		SkipInvalidRows: true, // they will be reported in lastResp.InsertErrors
		Rows:            rows,
	})
	if err != nil {
		if gerr, _ := err.(*googleapi.Error); gerr != nil {
			if gerr.Code >= 500 {
				err = transient.Tag.Apply(err)
			}
		}
		return errors.Annotate(err, "sending to BigQuery").Err()
	}

	if len(resp.InsertErrors) > 0 {
		// Use only first error as a sample. Dumping them all is impractical.
		blob, _ := json.MarshalIndent(resp.InsertErrors[0].Errors, "", "  ")
		logging.Errorf(ctx, "%d rows weren't accepted, sample error:\n%s", len(resp.InsertErrors), blob)
	}
	return nil
}

// insertRPC does the actual BigQuery insert.
//
// It is mocked in tests.
func (r *RAMBufferedBQInserter) insertRPC(ctx context.Context, req *bqapi.TableDataInsertAllRequest) (
	*bqapi.TableDataInsertAllResponse, error) {
	ctx, cancel := clock.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	tr, err := auth.GetRPCTransport(ctx, auth.AsSelf, auth.WithScopes(bqapi.BigqueryScope))
	if err != nil {
		return nil, err
	}
	bq, err := bqapi.New(&http.Client{Transport: tr})
	if err != nil {
		return nil, err
	}
	call := bq.Tabledata.InsertAll(r.ProjectID, r.DatasetID, r.TableID, req)
	return call.Context(ctx).Do()
}

// valuesToJSON prepares row map in a format used by BQ API.
func valuesToJSON(in map[string]bigquery.Value) (map[string]bqapi.JsonValue, error) {
	if len(in) == 0 {
		return nil, nil
	}
	out := make(map[string]bqapi.JsonValue, len(in))
	for k, v := range in {
		blob, err := json.Marshal(v)
		if err != nil {
			return nil, errors.Annotate(err, "failed to JSON-serialize key %q", k).Err()
		}
		out[k] = json.RawMessage(blob)
	}
	return out, nil
}
