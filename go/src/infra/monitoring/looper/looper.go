package looper

import (
	"expvar"
	"time"

	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"
)

var (
	expvars = expvar.NewMap("looper")
)

// Results describe the results of running a loop.
type Results struct {
	// Success is true if there were no errors, or if all failed attempts
	// succeeded on within maxErrs subsequent attempts.
	Success bool
	// Overruns counts the total number of overruns.
	Overruns int
	// Errs counts total number of errors, some may have been retried.
	Errs int
}

// Runner is the type for functions executed by looper.Run.
type Runner func(ctx context.Context) error

// Run will run f every cyle (at least once), and fail if maxErrs are returned by
// f in a row. It returns Results indiciating success, number of overruns and
// errors. Use context.WithCancel/Timeout/Deadline to limit the overall run time.
func Run(ctx context.Context, f Runner, cycle time.Duration, maxErrs int, c clock.Clock) (ret *Results) {
	// TODO: ts_mon stuff.
	ret = &Results{Success: true}

	tmr := c.NewTimer()
	defer tmr.Stop()

	nextCycle := cycle
	consecErrs := 0
	log := logging.Get(ctx)

	run := func() {
		expvars.Add("Running", 1)
		defer expvars.Add("Running", -1)
		defer expvars.Add("Runs", 1)

		t0 := c.Now()
		// TODO(seanmccullough) Optionally cancel overruns via context.WithTimeout.
		err := f(ctx)
		dur := c.Now().Sub(t0)
		if dur > cycle {
			log.Errorf("Task overran by %v (%v - %v)", (dur - cycle), dur, cycle)
			ret.Overruns++
			expvars.Add("Overruns", 1)
		}

		if err != nil {
			log.Errorf("Got an error: %v", err)
			ret.Errs++
			expvars.Add("Errors", 1)
			if consecErrs++; consecErrs >= maxErrs {
				ret.Success = false
				return
			}
		} else {
			consecErrs = 0
		}

		nextCycle = cycle - dur
		if tmr.Reset(nextCycle) {
			log.Errorf("Timer was still active")
		}
	}

	// Run f at least once.
	run()

	// Keep running f until ctx is done.
	for {
		select {
		case <-ctx.Done():
			tmr.Stop()
			return ret
		case <-tmr.GetC():
			run()
		}
	}
}
