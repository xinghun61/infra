package looper

import (
	"fmt"
	"testing"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"golang.org/x/net/context"
)

// Run f once, then cancel.
func TestLoopOnce(t *testing.T) {
	ctx, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func(ctx context.Context) error {
		nCalls++
		return nil
	}

	ctx, cancel := context.WithCancel(ctx)
	c.SetTimerCallback(func(d time.Duration, t clock.Timer) {
		cancel()
	})
	res := Run(ctx, f, 1*time.Second, 1, c)
	if !res.Success {
		t.Errorf("Should have succeeded.")
	}
	if nCalls != 1 {
		t.Errorf("Want %d got %d", 1, nCalls)
	}
}

// Run for 5s, every 1s. Should run 5 times before returning Success.
func TestLoopMultiple(t *testing.T) {
	ctx, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func(ctx context.Context) error {
		nCalls++
		return nil
	}

	ctx, cancel := context.WithCancel(ctx)
	i := 0
	c.SetTimerCallback(func(d time.Duration, t clock.Timer) {
		if i++; i >= 5 {
			cancel()
		} else {
			c.Add(d)
		}
	})
	res := Run(ctx, f, 1*time.Second, 1, c)
	if !res.Success {
		t.Errorf("Should have succeeded.")
	}
	if nCalls != 5 {
		t.Errorf("Want %d got %d", 5, nCalls)
	}
}

// Run for 10s, every 1s. Every other task takes 1.5s to run. 3 + 3*1.5?
func TestLoopOverrunSome(t *testing.T) {
	ctx, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func(ctx context.Context) error {
		if nCalls%2 == 0 {
			c.Add(1500 * time.Millisecond)
		} else {
			c.Add(500 * time.Millisecond)
		}
		nCalls++
		return nil
	}
	ctx, cancel := context.WithCancel(ctx)
	i := 0
	c.SetTimerCallback(func(d time.Duration, t clock.Timer) {
		if i++; i >= 10 {
			cancel()
		} else {
			c.Add(d)
		}
	})

	res := Run(ctx, f, 1*time.Second, 3, c)
	if !res.Success {
		t.Errorf("Should have succeeded.")
	}
	if nCalls != 10 {
		t.Errorf("Want %d calls got %d", 10, nCalls)
	}
	if res.Errs != 0 {
		t.Errorf("Want %d Errs got %d", 0, res.Errs)
	}
	if res.Overruns != 5 {
		t.Errorf("Want %d Overruns got %d", 5, res.Overruns)
	}
}

func TestLoopOverrunAll(t *testing.T) {
	ctx, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func(ctx context.Context) error {
		if nCalls < 4 {
			c.Add(1001 * time.Millisecond)
		}
		nCalls++
		return nil
	}

	ctx, cancel := context.WithCancel(ctx)
	i := 0
	c.SetTimerCallback(func(d time.Duration, t clock.Timer) {
		if i++; i >= 5 {
			cancel()
		} else {
			c.Add(d)
		}
	})
	res := Run(ctx, f, 1*time.Second, 3, c)
	if !res.Success {
		t.Errorf("Should have succeeded.")
	}
	if nCalls != 5 {
		t.Errorf("Want %d calls got %d", 5, nCalls)
	}
	if res.Errs != 0 {
		t.Errorf("Want %d Errs got %d", 0, res.Errs)
	}
	if res.Overruns != 4 {
		t.Errorf("Want %d Overruns got %d", 4, res.Overruns)
	}
}

// Run for 10s, every 1s. Return errors on 2nd, 4th, 6th, 7th and 8th calls.
func TestLoopMaxErrors(t *testing.T) {
	ctx, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func(ctx context.Context) error {
		nCalls++
		if nCalls%2 == 0 || nCalls > 5 {
			return fmt.Errorf("this is an error: %d", nCalls)
		}
		return nil
	}

	ctx, cancel := context.WithCancel(ctx)
	i := 0
	c.SetTimerCallback(func(d time.Duration, t clock.Timer) {
		if i++; i >= 8 {
			cancel()
		} else {
			c.Add(d)
		}
	})
	res := Run(ctx, f, 1*time.Second, 3, c)
	if res.Success {
		t.Errorf("Should have failed.")
	}
	if nCalls != 8 {
		t.Errorf("Want %d calls got %d", 6, nCalls)
	}
	if res.Errs != 5 {
		t.Errorf("Want %d Errs got %d", 4, res.Errs)
	}
}
