package handlers

import (
	"bytes"
	"encoding/json"
	"infra/appengine/rotang"
	"io"
	"net/http"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type testEmail struct {
	Subject string
	Body    string
}

// HandleEmailTestJSON runs the email test and returns the result as json.
func (h *State) HandleEmailTestJSON(ctx *router.Context) {
	rota, err := h.rota(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	now := clock.Now(ctx.Context)
	subject, body, err := h.fillEmail(ctx, rota, now)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	var res bytes.Buffer
	if err := json.NewEncoder(&res).Encode(testEmail{
		Subject: subject,
		Body:    body,
	}); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	logging.Infof(ctx.Context, "Subject: %q, Body: %q", subject, body)

	io.Copy(ctx.Writer, &res)
}

func (h *State) fillEmail(ctx *router.Context, rota *rotang.Configuration, t time.Time) (string, string, error) {
	ss, err := h.shiftStore(ctx.Context).ShiftsFromTo(ctx.Context, rota.Config.Name, t, time.Time{})
	if err != nil {
		if status.Code(err) != codes.NotFound {
			return "", "", err
		}
	}
	if len(ss) < 1 {
		logging.Infof(ctx.Context, "No current shifts found for rota: %q, using a dummy shift", rota.Config.Name)
		ss = []rotang.ShiftEntry{
			{
				Name:      "Shift Dummy Entry",
				StartTime: t,
				EndTime:   t.Add(5 * fullDay),
				OnCall: []rotang.ShiftMember{
					{
						ShiftName: "MTV All Day",
						Email:     "daddr_a@dummy.com",
					}, {
						ShiftName: "MTV All Day",
						Email:     "daddr_b@dummy.com",
					},
				},
			},
		}
	}

	m, err := h.memberStore(ctx.Context).Member(ctx.Context, auth.CurrentUser(ctx.Context).Email)
	if err != nil {
		if status.Code(err) != codes.NotFound {
			return "", "", err
		}
		logging.Infof(ctx.Context, "User %q not in any rotations, using a dummy memmber", auth.CurrentUser(ctx.Context).Email)
		m = &rotang.Member{
			Name:  "Dummy Member",
			Email: "dummy@dummy.com",
		}
	}

	subject, body, err := emailFromTemplate(rota, &rotang.Info{
		RotaName:    rota.Config.Name,
		ShiftConfig: rota.Config.Shifts,
		ShiftEntry:  ss[0],
		Member:      *m,
	})
	if err != nil {
		return "", "", err
	}
	return subject, body, nil
}
