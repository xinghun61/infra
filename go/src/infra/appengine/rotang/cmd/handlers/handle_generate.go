package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"infra/appengine/rotang"
	"net/http"
	"strconv"
	"time"

	"go.chromium.org/luci/server/router"
)

const elementTimeFormat = "2006-01-02"

// HandleGenerate generates rota schedules.
// Used by the `shiftgenerate-element`
func (h *State) HandleGenerate(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if ctx.Request.Method != "POST" {
		http.Error(ctx.Writer, "HandleGenerate handles POST requests only, req was:", http.StatusBadRequest)
		return
	}

	if err := ctx.Request.ParseForm(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	rota := ctx.Request.FormValue("rota")
	if rota == "" {
		http.Error(ctx.Writer, "rota not set", http.StatusBadRequest)
		return
	}

	cfg, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rota)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	if len(cfg) != 1 {
		http.Error(ctx.Writer, "wrong number of configurations returned", http.StatusInternalServerError)
		return
	}

	if !adminOrOwner(ctx, cfg[0]) {
		http.Error(ctx.Writer, "not admin or owner", http.StatusForbidden)
		return
	}

	nrSchedStr := ctx.Request.FormValue("nrShifts")
	if nrSchedStr == "" {
		nrSchedStr = strconv.Itoa(cfg[0].Config.ShiftsToSchedule)
	}
	nrSched, err := strconv.Atoi(nrSchedStr)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	generator := ctx.Request.FormValue("generator")
	if generator == "" {
		generator = cfg[0].Config.Shifts.Generator
	}

	var start time.Time
	var shifts []rotang.ShiftEntry
	switch ctx.Request.FormValue("startTime") {
	case "":
		var err error
		if shifts, err = h.shiftStore(ctx.Context).AllShifts(ctx.Context, rota); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
	default:
		var err error
		if start, err = time.ParseInLocation(elementTimeFormat, ctx.Request.FormValue("startTime"), mtvTime); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusBadRequest)
			return
		}
	}

	g, err := h.generators.Fetch(generator)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	memberStore := h.memberStore(ctx.Context)

	var members []rotang.Member
	for _, m := range cfg[0].Members {
		m, err := memberStore.Member(ctx.Context, m.Email)
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		members = append(members, *m)
	}

	ss, err := g.Generate(cfg[0], start, shifts, members, nrSched)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	res := RotaShifts{
		Rota:        rota,
		SplitShifts: makeSplitShifts(ss, cfg[0].Members),
	}

	var resBuf bytes.Buffer
	if err := json.NewEncoder(&resBuf).Encode(res); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	fmt.Fprintln(ctx.Writer, resBuf.String())
}
