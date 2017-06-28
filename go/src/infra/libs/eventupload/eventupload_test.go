// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package eventupload

import (
	"context"
	"reflect"
	"testing"
	"time"

	"github.com/luci/luci-go/common/tsmon"

	"cloud.google.com/go/bigquery"
)

type eventUploader interface {
	Put(ctx context.Context, src interface{}) error
}

type mockUploader chan []fakeEvent

func testContext() context.Context {
	ctx := context.Background()
	ctx = tsmon.WithState(ctx, tsmon.NewState())
	return ctx
}

func (u mockUploader) Put(ctx context.Context, src interface{}) error {
	srcs := src.([]interface{})
	var fes []fakeEvent
	for _, fe := range srcs {
		fes = append(fes, fe.(fakeEvent))
	}
	u <- fes
	return nil
}

type fakeEvent struct{}

func expectPutCalled(t *testing.T, u mockUploader, want []fakeEvent) {
	select {
	case got := <-u:
		if !reflect.DeepEqual(got, want) {
			t.Errorf("got: %v; want: %v", got, want)
		}
	case <-time.After(50 * time.Millisecond):
		t.Errorf("timed out waiting for upload")
	}
}

func TestClose(t *testing.T) {
	t.Parallel()

	ctx := testContext()
	u := make(mockUploader, 1)
	bu, err := NewBatchUploader(ctx, u)
	if err != nil {
		t.Fatal(err)
	}

	closed := false
	defer func() {
		if !closed {
			bu.Close()
		}
	}()

	bu.TickC = make(chan time.Time)

	bu.Stage(fakeEvent{})
	if got, want := len(bu.pending), 1; got != want {
		t.Errorf("got: %d; want: %d", got, want)
	}

	bu.Close()
	closed = true

	if got, want := len(bu.pending), 0; got != want {
		t.Errorf("got: %d; want: %d", got, want)
	}
	expectPutCalled(t, u, []fakeEvent{{}})
}

func TestUpload(t *testing.T) {
	t.Parallel()

	ctx := testContext()
	u := make(mockUploader, 1)
	bu, err := NewBatchUploader(ctx, &u)
	if err != nil {
		t.Fatal(err)
	}
	defer bu.Close()

	tickc := make(chan time.Time)
	bu.TickC = tickc

	bu.Stage(fakeEvent{})
	if got, want := len(u), 0; got != want {
		t.Errorf("got: %d; want: %d", got, want)
	}
	tickc <- time.Time{}
	expectPutCalled(t, u, []fakeEvent{{}})
}

func TestPrepareSrc(t *testing.T) {
	t.Parallel()

	type testCase struct {
		src     interface{}
		wantLen int
	}
	tcs := []testCase{
		{
			src:     fakeEvent{},
			wantLen: 1,
		},
		{
			src:     []fakeEvent{{}, {}},
			wantLen: 2,
		},
	}
	for _, tc := range tcs {
		s, err := bigquery.InferSchema(fakeEvent{})
		if err != nil {
			t.Fatal(err)
		}
		sss := prepareSrc(s, tc.src)
		if got, want := len(sss), tc.wantLen; got != want {
			t.Errorf("got: %d; want: %d", got, want)
		}
	}
}

func TestCounterMetric(t *testing.T) {
	t.Parallel()

	ctx := testContext()
	u := make(mockUploader, 1)
	bu, err := NewBatchUploader(ctx, &u)
	if err != nil {
		t.Fatal(err)
	}
	defer bu.Close()

	bu.UploadMetricName = "fakeCounter"

	bu.start() // To actually create the metric
	if got, want := bu.uploads.Info().Name, "fakeCounter"; got != want {
		t.Errorf("got: %s; want: %s", got, want)
	}
}

func TestStage(t *testing.T) {
	t.Parallel()

	type testCase struct {
		src     interface{}
		wantLen int
	}
	tcs := []testCase{
		{
			src:     fakeEvent{},
			wantLen: 1,
		},
		{
			src:     []fakeEvent{{}, {}},
			wantLen: 2,
		},
	}
	for _, tc := range tcs {
		ctx := testContext()
		u := make(mockUploader, 1)
		bu, err := NewBatchUploader(ctx, &u)
		if err != nil {
			t.Fatal(err)
		}
		defer bu.Close()

		bu.Stage(tc.src)
		if got, want := len(bu.pending), tc.wantLen; got != want {
			t.Errorf("got: %d; want: %d", got, want)
		}
		got := reflect.ValueOf(bu.pending[0]).Kind()
		want := reflect.Struct
		if got != want {
			t.Errorf("got: %d; want: %d", got, want)
		}
	}
}
