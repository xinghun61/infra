// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package eventupload

import (
	"fmt"
	"testing"
	"time"

	"cloud.google.com/go/bigquery"
	"golang.org/x/net/context"

	"go.chromium.org/luci/common/tsmon"

	. "github.com/smartystreets/goconvey/convey"
)

// MockUploader is an EventUploader that can be used for testing.
type MockUploader chan []fakeEvent

// Put sends events on the MockUploader.
func (u MockUploader) Put(ctx context.Context, src interface{}) error {
	srcs := src.([]interface{})
	var fes []fakeEvent
	for _, fe := range srcs {
		fes = append(fes, fe.(fakeEvent))
	}
	u <- fes
	return nil
}

type fakeEvent struct{}

// ShouldHavePut verifies that Put was called with the expected set of events.
func ShouldHavePut(actual interface{}, expected ...interface{}) string {
	u := actual.(MockUploader)

	select {
	case got := <-u:
		return ShouldResemble([]interface{}{got}, expected)
	case <-time.After(50 * time.Millisecond):
		return "timed out waiting for upload"
	}
}

func TestMetric(t *testing.T) {
	t.Parallel()
	ctx := tsmon.WithState(context.Background(), tsmon.NewState())
	u := Uploader{}
	u.UploadsMetricName = "fakeCounter"
	Convey("Test metric creation", t, func() {
		Convey("Expect uploads metric was created", func() {
			_ = u.getCounter(ctx) // To actually create the metric
			So(u.uploads.Info().Name, ShouldEqual, "fakeCounter")
		})
	})
}

func TestClose(t *testing.T) {
	t.Parallel()

	Convey("Test Close", t, func() {
		u := make(MockUploader, 1)
		bu, err := NewBatchUploader(context.Background(), u, make(chan time.Time))
		if err != nil {
			t.Fatal(err)
		}

		closed := false
		defer func() {
			if !closed {
				bu.Close()
			}
		}()

		Convey("Expect Stage to add event to pending queue", func() {
			bu.Stage(fakeEvent{})
			So(bu.pending, ShouldHaveLength, 1)
		})

		Convey("Expect Close to flush pending queue", func() {
			bu.Stage(fakeEvent{})
			bu.Close()
			closed = true
			So(bu.pending, ShouldHaveLength, 0)
			So(u, ShouldHavePut, []fakeEvent{{}})
			So(bu.isClosed(), ShouldBeTrue)
			So(func() { bu.Stage(fakeEvent{}) }, ShouldPanic)
		})
	})
}

func TestUpload(t *testing.T) {
	t.Parallel()

	Convey("Test Upload", t, func() {
		u := make(MockUploader, 1)
		tickc := make(chan time.Time)
		bu, err := NewBatchUploader(context.Background(), &u, tickc)
		if err != nil {
			t.Fatal(err)
		}
		defer bu.Close()

		bu.Stage(fakeEvent{})
		Convey("Expect Put to wait for tick to call upload", func() {
			So(u, ShouldHaveLength, 0)
			tickc <- time.Time{}
			So(u, ShouldHavePut, []fakeEvent{{}})
		})
	})
}

func TestPrepareSrc(t *testing.T) {
	t.Parallel()

	notStruct := 0
	tcs := []struct {
		desc    string
		src     interface{}
		wantLen int
	}{
		{
			desc:    "prepareSrc accepts structs",
			src:     fakeEvent{},
			wantLen: 1,
		},
		{
			desc:    "prepareSrc accepts pointers to structs",
			src:     &fakeEvent{},
			wantLen: 1,
		},
		{
			desc:    "prepareSrc accepts slices of structs",
			src:     []fakeEvent{{}, {}},
			wantLen: 2,
		},
		{
			desc: "prepareSrc accepts slices of pointers to structs",
			src: []*fakeEvent{
				{},
				{},
			},
			wantLen: 2,
		},
		{
			desc:    "prepareSrc does not accept pointers to non-struct types",
			src:     &notStruct,
			wantLen: 0,
		},
		{
			desc:    "prepareSrc does not accept slices of non-struct or non-pointer types",
			src:     []string{"not a struct or pointer"},
			wantLen: 0,
		},
		{
			desc:    "prepareSrc does not accept slices of non-struct or non-pointer types (2)",
			src:     []*int{&notStruct},
			wantLen: 0,
		},
	}

	Convey("Test PrepareSrc", t, func() {
		for _, tc := range tcs {
			Convey(tc.desc, func() {
				sss, _ := prepareSrc(tc.src)
				So(sss, ShouldHaveLength, tc.wantLen)
			})
		}
	})
}

func TestStage(t *testing.T) {
	t.Parallel()

	tcs := []struct {
		desc    string
		src     interface{}
		wantLen int
	}{
		{
			desc:    "single event",
			src:     fakeEvent{},
			wantLen: 1,
		},
		{
			desc:    "slice of events",
			src:     []fakeEvent{{}, {}},
			wantLen: 2,
		},
	}

	Convey("Stage can accept single events and slices of events", t, func() {
		u := make(MockUploader, 1)
		bu, err := NewBatchUploader(context.Background(), &u, make(chan time.Time))
		if err != nil {
			t.Fatal(err)
		}
		defer bu.Close()

		for _, tc := range tcs {
			Convey(fmt.Sprintf("Test %s", tc.desc), func() {
				bu.Stage(tc.src)
				So(bu.pending, ShouldHaveLength, tc.wantLen)
				So(bu.pending[len(bu.pending)-1], ShouldHaveSameTypeAs, fakeEvent{})
			})
		}
	})
}

func TestBatch(t *testing.T) {
	t.Parallel()

	Convey("Test batch", t, func() {
		rowLimit := 2
		sss := make([]*bigquery.StructSaver, 3)
		for i := 0; i < 3; i++ {
			sss[i] = &bigquery.StructSaver{}
		}

		want := [][]*bigquery.StructSaver{
			{
				&bigquery.StructSaver{},
				&bigquery.StructSaver{},
			},
			{
				&bigquery.StructSaver{},
			},
		}
		rowSets := batch(sss, rowLimit)
		So(rowSets, ShouldResemble, want)
	})
}
