package main

import (
	"fmt"
	"testing"
	"time"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"
	"golang.org/x/net/context"
)

// Should run f at least once, even if the duration is 0.
func TestLoopOnce(t *testing.T) {
	_, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func() error {
		log.Infof("tick")
		nCalls++
		return nil
	}

	timerStartedC := make(chan bool, 1)
	c.SetTimerCallback(func(_ clock.Timer) {
		timerStartedC <- true
	})

	done := make(chan struct{})
	go func() {
		res := loop(f, 1*time.Second, 0*time.Second, 1, c)
		if !res.success {
			t.Errorf("Should have succeeded.")
		}
		if nCalls != 1 {
			t.Errorf("Want %d got %d", 1, nCalls)
		}
		close(done)
	}()

	<-timerStartedC

	c.Add(1 * time.Second)

	<-done
}

// Run for 5s, every 1s. Should run 5 times before returning success.
func TestLoopMultiple(t *testing.T) {
	_, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func() error {
		nCalls++
		c.Add(500 * time.Millisecond)
		return nil
	}

	timerStartedC := make(chan bool, 1)
	c.SetTimerCallback(func(_ clock.Timer) {
		timerStartedC <- true
	})

	done := make(chan struct{})
	go func() {
		res := loop(f, 1*time.Second, 5*time.Second, 1, c)
		if !res.success {
			t.Errorf("Should have succeeded.")
		}
		if nCalls != 5 {
			t.Errorf("Want %d got %d", 5, nCalls)
		}
		close(done)
	}()

	// Read off the initial 0s timeout for the first run, which should be immediate.
	<-timerStartedC

	// Now read off the rest of the timer ticks.
	for i := 0; i < 4; i++ {
		<-timerStartedC
		c.Add(1 * time.Second)
	}

	// Roll past the duration timeout.
	c.Add(1 * time.Second)

	<-done
}

// Run for 10s, every 1s. Every other task takes 1.5s to run. 3 + 3*1.5?
func TestLoopOverrunSome(t *testing.T) {
	_, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func() error {
		nCalls++
		if nCalls%2 == 0 {
			c.Add(1500 * time.Millisecond)
		} else {
			c.Add(500 * time.Millisecond)
		}

		return nil
	}

	timerStartedC := make(chan bool, 1)
	c.SetTimerCallback(func(_ clock.Timer) {
		timerStartedC <- true
	})

	done := make(chan struct{})
	go func() {
		res := loop(f, 1*time.Second, 10*time.Second, 3, c)
		if !res.success {
			t.Errorf("Should have succeeded.")
		}
		if nCalls != 8 {
			t.Errorf("Want %d calls got %d", 6, nCalls)
		}
		if res.errs != 0 {
			t.Errorf("Want %d errs got %d", 0, res.errs)
		}
		if res.overruns != 4 {
			t.Errorf("Want %d overruns got %d", 4, res.overruns)
		}
		close(done)
	}()

	// Read off the initial 0s timeout for the first run, which should be immediate.
	<-timerStartedC

	// Now read off the rest of the timer ticks.
	for i := 0; i < 7; i++ {
		<-timerStartedC
		c.Add(500 * time.Millisecond)
	}
	<-done
}

func TestLoopOverrunAll(t *testing.T) {
	_, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func() error {
		nCalls++
		c.Add(2 * time.Second)

		return nil
	}

	timerStartedC := make(chan bool, 1)
	c.SetTimerCallback(func(_ clock.Timer) {
		timerStartedC <- true
	})

	done := make(chan struct{})
	go func() {
		res := loop(f, 1*time.Second, 10*time.Second, 3, c)
		if !res.success {
			t.Errorf("Should have succeeded.")
		}
		if nCalls != 5 {
			t.Errorf("Want %d calls got %d", 6, nCalls)
		}
		if res.errs != 0 {
			t.Errorf("Want %d errs got %d", 0, res.errs)
		}
		if res.overruns != 5 {
			t.Errorf("Want %d overruns got %d", 5, res.overruns)
		}
		close(done)
	}()

	// Read off the initial 0s timeout for the first run, which should be immediate.
	<-timerStartedC

	// Now read off the rest of the timer ticks.
	for i := 0; i < 4; i++ {
		<-timerStartedC
		c.Add(1 * time.Millisecond)
	}
	<-done
}

// Run for 10s, every 1s. Return errors on 2nd, 4th, 6th, 7th and 8th calls.
func TestLoopMaxErrors(t *testing.T) {
	_, c := testclock.UseTime(context.Background(), time.Unix(0, 0))

	nCalls := 0
	f := func() error {
		nCalls++
		if nCalls%2 == 0 || nCalls > 5 {
			return fmt.Errorf("this is an error: %d", nCalls)
		}

		return nil
	}

	timerStartedC := make(chan bool, 1)
	c.SetTimerCallback(func(_ clock.Timer) {
		timerStartedC <- true
	})

	done := make(chan struct{})
	go func() {
		res := loop(f, 1*time.Second, 10*time.Second, 3, c)
		fmt.Printf("res: %+v", res)
		if res.success {
			t.Errorf("Should have failed.")
		}
		if nCalls != 8 {
			t.Errorf("Want %d calls got %d", 6, nCalls)
		}
		if res.errs != 5 {
			t.Errorf("Want %d errs got %d", 4, res.errs)
		}
		close(done)
	}()

	// Read off the initial 0s timeout for the first run, which should be immediate.
	<-timerStartedC

	// Now read off the rest of the timer ticks.
	for i := 0; i < 7; i++ {
		<-timerStartedC
		c.Add(1 * time.Second)
	}

	c.Add(1 * time.Second)
	<-done
}
