package algo

import (
	"infra/appengine/rotang"
	"testing"
	"time"

	"github.com/kylelemons/godebug/pretty"
)

func TestSplitShiftModify(t *testing.T) {

	// A MTV Time monday.
	baseTime := time.Date(2006, 7, 31, 0, 0, 0, 0, mtvTime)

	tests := []struct {
		name   string
		fail   bool
		cfg    *rotang.ShiftConfig
		shifts []rotang.ShiftEntry
		want   []rotang.ShiftEntry
	}{{
		name: "Split 5 day shifts",
		cfg: &rotang.ShiftConfig{
			TZ: *mtvTime,
		},
		shifts: []rotang.ShiftEntry{
			{
				StartTime: baseTime,
				EndTime:   baseTime.Add(5 * fullDay),
			}, {
				StartTime: baseTime.Add(7 * fullDay),
				EndTime:   baseTime.Add(12 * fullDay),
			},
		},
		want: []rotang.ShiftEntry{
			{
				StartTime: baseTime,
				EndTime:   baseTime.Add(fullDay),
			}, {
				StartTime: baseTime.Add(fullDay),
				EndTime:   baseTime.Add(2 * fullDay),
			}, {
				StartTime: baseTime.Add(2 * fullDay),
				EndTime:   baseTime.Add(3 * fullDay),
			}, {
				StartTime: baseTime.Add(3 * fullDay),
				EndTime:   baseTime.Add(4 * fullDay),
			}, {
				StartTime: baseTime.Add(4 * fullDay),
				EndTime:   baseTime.Add(5 * fullDay),
			}, {
				StartTime: baseTime.Add(7 * fullDay),
				EndTime:   baseTime.Add(8 * fullDay),
			}, {
				StartTime: baseTime.Add(8 * fullDay),
				EndTime:   baseTime.Add(9 * fullDay),
			}, {
				StartTime: baseTime.Add(9 * fullDay),
				EndTime:   baseTime.Add(10 * fullDay),
			}, {
				StartTime: baseTime.Add(10 * fullDay),
				EndTime:   baseTime.Add(11 * fullDay),
			}, {
				StartTime: baseTime.Add(11 * fullDay),
				EndTime:   baseTime.Add(12 * fullDay),
			},
		},
	}, {
		name: "2 day split",
		cfg: &rotang.ShiftConfig{
			TZ: *mtvTime,
		},
		shifts: []rotang.ShiftEntry{
			{
				// Monday, Tuesday
				StartTime: baseTime,
				EndTime:   baseTime.Add(2 * fullDay),
			}, {
				// Wednesday, Thursday
				StartTime: baseTime.Add(2 * fullDay),
				EndTime:   baseTime.Add(4 * fullDay),
			}, {
				// Friday, Saturday
				StartTime: baseTime.Add(4 * fullDay),
				EndTime:   baseTime.Add(6 * fullDay),
			},
		},
		want: []rotang.ShiftEntry{
			{
				StartTime: baseTime,
				EndTime:   baseTime.Add(fullDay),
			}, {
				StartTime: baseTime.Add(fullDay),
				EndTime:   baseTime.Add(2 * fullDay),
			}, {
				StartTime: baseTime.Add(2 * fullDay),
				EndTime:   baseTime.Add(3 * fullDay),
			}, {
				StartTime: baseTime.Add(3 * fullDay),
				EndTime:   baseTime.Add(4 * fullDay),
			}, {
				StartTime: baseTime.Add(4 * fullDay),
				EndTime:   baseTime.Add(5 * fullDay),
			}, {
				StartTime: baseTime.Add(5 * fullDay),
				EndTime:   baseTime.Add(6 * fullDay),
			},
		},
	}, {
		name: "Already 1 day shifts",
		cfg: &rotang.ShiftConfig{
			TZ: *mtvTime,
		},
		shifts: []rotang.ShiftEntry{
			{
				// Monday, Tuesday
				StartTime: baseTime,
				EndTime:   baseTime.Add(fullDay),
			}, {
				// Wednesday, Thursday
				StartTime: baseTime.Add(fullDay),
				EndTime:   baseTime.Add(2 * fullDay),
			}, {
				// Friday, Saturday
				StartTime: baseTime.Add(2 * fullDay),
				EndTime:   baseTime.Add(3 * fullDay),
			},
		},
		want: []rotang.ShiftEntry{
			{
				StartTime: baseTime,
				EndTime:   baseTime.Add(fullDay),
			}, {
				StartTime: baseTime.Add(fullDay),
				EndTime:   baseTime.Add(2 * fullDay),
			}, {
				StartTime: baseTime.Add(2 * fullDay),
				EndTime:   baseTime.Add(3 * fullDay),
			},
		},
	},
	}

	ws := NewSplitShift()

	for _, tst := range tests {
		shifts, err := ws.Modify(tst.cfg, tst.shifts)
		if got, want := (err != nil), tst.fail; got != want {
			t.Errorf("%s: Modify(cfg, shifts) = %t want: %t, err: %v", tst.name, got, want, err)
			continue
		}
		if err != nil {
			continue
		}
		if diff := pretty.Compare(tst.want, shifts); diff != "" {
			t.Errorf("%s: Modify(cfg, shifts) differ -want +got, %s", tst.name, diff)
		}
	}
}
