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
	"fmt"
	"sync"
	"sync/atomic"
	"testing"

	"cloud.google.com/go/bigquery"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/common/retry/transient"
	bqapi "google.golang.org/api/bigquery/v2"
	"google.golang.org/api/googleapi"
)

func TestRamBufferedBQInserter(t *testing.T) {
	Convey("With mock context", t, func() {
		ctx := context.Background()
		ctx = logging.SetLevel(gologger.StdConfig.Use(ctx), logging.Debug)
		ctx, cancel := context.WithCancel(ctx)
		defer cancel()

		bi, err := NewRAMBufferedBQInserter(ctx, "project", "dataset", "table")
		So(err, ShouldBeNil)

		Convey("drain unused works", func() {
			bi.insertRPCMock = func(_ context.Context, req *bqapi.TableDataInsertAllRequest) (*bqapi.TableDataInsertAllResponse, error) {
				panic("must not be called")
			}
			bi.CloseAndDrain(ctx)
		})

		Convey("sends everything", func() {
			sent := int32(0)
			bi.insertRPCMock = func(_ context.Context, req *bqapi.TableDataInsertAllRequest) (*bqapi.TableDataInsertAllResponse, error) {
				atomic.AddInt32(&sent, int32(len(req.Rows)))
				return &bqapi.TableDataInsertAllResponse{}, nil
			}
			for i := 1; i <= 10; i++ {
				So(bi.Insert(ctx, mkTestEntry(i, fmt.Sprintf("insertId:%d", i))), ShouldBeNil)
			}
			bi.CloseAndDrain(ctx)
			So(sent, ShouldEqual, 10)
		})

		Convey("fills missing insertIDs", func() {
			var lock sync.Mutex
			insertIDs := stringset.Set{}
			bi.insertRPCMock = func(_ context.Context, req *bqapi.TableDataInsertAllRequest) (*bqapi.TableDataInsertAllResponse, error) {
				lock.Lock()
				for _, row := range req.Rows {
					insertIDs.Add(row.InsertId)
				}
				lock.Unlock()
				return &bqapi.TableDataInsertAllResponse{}, nil
			}
			entries := make([]bigquery.ValueSaver, 10)
			for i := 0; i < 5; i++ {
				entries[2*i] = mkTestEntry(2*i, fmt.Sprintf("given:%d", 2*i))
				entries[2*i+1] = mkTestEntry(2*i + 1)
			}
			So(bi.Insert(ctx, entries...), ShouldBeNil)
			bi.CloseAndDrain(ctx)
			So(insertIDs.Has(""), ShouldBeFalse)
			So(insertIDs.HasAll("given:0", "given:2", "given:4", "given:6", "given:8"), ShouldBeTrue)
			So(insertIDs.Len(), ShouldEqual, 10)
		})

		Convey("retries transient errors", func() {
			// Simulate transient failures.
			var lock sync.Mutex
			sent := 0
			tries := map[string]int{}
			bi.insertRPCMock = func(_ context.Context, req *bqapi.TableDataInsertAllRequest) (*bqapi.TableDataInsertAllResponse, error) {
				lock.Lock()
				cur := tries[req.Rows[0].InsertId]
				tries[req.Rows[0].InsertId]++
				lock.Unlock()
				switch cur {
				case 0:
					return nil, transient.Tag.Apply(errors.New("oops"))
				case 1:
					return nil, &googleapi.Error{
						Code: 503,
						Body: "at least network works",
					}
				case 2:
					sent += len(req.Rows)
					return &bqapi.TableDataInsertAllResponse{
						InsertErrors: []*bqapi.TableDataInsertAllResponseInsertErrors{
							{Index: 0, Errors: []*bqapi.ErrorProto{{Reason: "bad value"}}},
						},
					}, nil
				default:
					panic(fmt.Errorf("%d is too many tries", cur))
				}
			}

			for i := 1; i <= 10; i++ {
				So(bi.Insert(ctx, mkTestEntry(i, fmt.Sprintf("insertId:%d", i))), ShouldBeNil)
			}
			bi.CloseAndDrain(ctx)
			So(sent, ShouldEqual, 10)
			for _, v := range tries {
				So(v, ShouldEqual, 3) // Each batch must be tried till success.
			}
		})

		Convey("load-shedding: drop ~oldest batch when overloaded", func() {
			slow := make(chan struct{})

			var lock sync.Mutex
			sent := stringset.Set{}
			bi.insertRPCMock = func(_ context.Context, req *bqapi.TableDataInsertAllRequest) (*bqapi.TableDataInsertAllResponse, error) {
				<-slow // simulate slow sending.
				lock.Lock()
				for _, row := range req.Rows {
					sent.Add(row.InsertId)
				}
				lock.Unlock()
				return &bqapi.TableDataInsertAllResponse{}, nil
			}

			// Must be > (batches * maxLeases + maxLiveItems). See also assertion at the end.
			n := 2100
			for i := 1; i <= n; i++ {
				So(bi.Insert(ctx, mkTestEntry(i, fmt.Sprintf("iid:%09d", i))), ShouldBeNil)
			}
			// At this point, sending of some batches could have started,
			// those batches will be unblocked below and succeed.
			close(slow)
			// As for the rest of old rows, they should already be forgotten.
			bi.CloseAndDrain(ctx)
			// Depending on how batches were cut and max number of senders,
			// we can be sure only about the very first item being sent and the very
			// last.
			So(sent.Has(fmt.Sprintf("iid:%09d", 1)), ShouldBeTrue)
			So(sent.Has(fmt.Sprintf("iid:%09d", n)), ShouldBeTrue)
			// Ensures test is actually useful even after parameters in prod code are tweaked
			// by forcing codepath that drops items.
			So(sent.Len(), ShouldBeLessThan, n)
		})
	})
}

func mkTestEntry(val int, insertID ...string) bigquery.ValueSaver {
	iid := ""
	switch len(insertID) {
	case 0:
	case 1:
		iid = insertID[0]
	default:
		panic("at most 1 insertID allowed")
	}
	return &testEntry{InsertID: iid, Data: map[string]bigquery.Value{
		"val":   val,
		"sqval": val * val,
	}}
}

type testEntry struct {
	InsertID string
	Data     map[string]bigquery.Value
}

// Save implements bigquery.ValueSaver interface.
func (e testEntry) Save() (map[string]bigquery.Value, string, error) {
	return e.Data, e.InsertID, nil
}
