package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
)

const elementTimeFormat = "2006-01-02"

// HandleGenerate generates rota schedules.
// Used by the `shiftgenerate-element`
func (h *State) HandleGenerate(ctx *router.Context) {
	rota, err := h.rota(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	var start time.Time
	var shifts []rotang.ShiftEntry
	switch ctx.Request.FormValue("startTime") {
	case "":
		var err error
		if shifts, err = h.shiftStore(ctx.Context).AllShifts(ctx.Context, rota.Config.Name); err != nil {
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

	memberStore := h.memberStore(ctx.Context)

	var members []rotang.Member
	for _, m := range rota.Members {
		m, err := memberStore.Member(ctx.Context, m.Email)
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		members = append(members, *m)
	}

	nrSchedStr := ctx.Request.FormValue("nrShifts")
	if nrSchedStr == "" {
		nrSchedStr = strconv.Itoa(rota.Config.ShiftsToSchedule)
	}
	nrSched, err := strconv.Atoi(nrSchedStr)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	generator := ctx.Request.FormValue("generator")
	if generator == "" {
		generator = rota.Config.Shifts.Generator
	}
	g, err := h.generators.Fetch(generator)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	ss, err := g.Generate(rota, start, shifts, members, nrSched)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	// TODO(olakar): Remove this when rotation TZ is implemented.
	rota.Config.Shifts.TZ = *mtvTime

	modifiers := strings.Split(ctx.Request.FormValue("modifiers"), ",")
	for _, m := range modifiers {
		if m == "" {
			continue
		}
		mod, err := h.generators.FetchModifier(m)
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		if ss, err = mod.Modify(&rota.Config.Shifts, ss); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		logging.Infof(ctx.Context, "modifier: %q applied to generated shifts for rota: %q", m, rota.Config.Name)
	}

	res := RotaShifts{
		Rota:        rota.Config.Name,
		SplitShifts: makeSplitShifts(ss, rota.Members),
	}

	var resBuf bytes.Buffer
	if err := json.NewEncoder(&resBuf).Encode(res); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	io.Copy(ctx.Writer, &resBuf)
}
