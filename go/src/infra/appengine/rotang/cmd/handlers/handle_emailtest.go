package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"infra/appengine/rotang"
	"io"
	"net/http"
	"sort"
	"time"

	"go.chromium.org/gae/service/mail"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type testEmail struct {
	Subject string
	Body    string
}

// HandleEmailTest lists the members rotations.
func (h *State) HandleEmailTest(ctx *router.Context) {
	usr := auth.CurrentUser(ctx.Context)
	if usr == nil || usr.Email == "" {
		http.Error(ctx.Writer, "not logged in", http.StatusForbidden)
		return
	}
	rotas, err := h.configStore(ctx.Context).MemberOf(ctx.Context, usr.Email)
	if err != nil && status.Code(err) != codes.NotFound {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	args, err := h.listRotations(ctx)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	cs, ok := args["Rotas"].([]*rotang.Configuration)
	if !ok {
		http.Error(ctx.Writer, "converting to rotang.Configuration failed", http.StatusInternalServerError)
		return
	}
	for _, cfg := range cs {
		rotas = append(rotas, cfg.Config.Name)
	}
	sort.Strings(rotas)
	var resRotas []string
	var seen string
	for _, r := range rotas {
		if seen == r {
			continue
		}
		seen = r
		resRotas = append(resRotas, r)
	}
	args["Rotas"] = resRotas
	templates.MustRender(ctx.Context, ctx.Writer, "pages/emailtest.html", args)
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

// HandleEmailTestSend tries to send an email to the caller.
func (h *State) HandleEmailTestSend(ctx *router.Context) {
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
	fmt.Println(subject, body)

	to, sender := h.setSender(ctx, auth.CurrentUser(ctx.Context).Email)

	if err := h.mailSender.Send(ctx.Context, &mail.Message{
		Sender:  sender,
		To:      []string{to},
		Subject: subject,
		Body:    body,
	}); err != nil {
		logging.Warningf(ctx.Context, "sending testmail from: %q to: %q failed: %v", sender, to, err)
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	logging.Infof(ctx.Context, "testmail sent from: %q to: %q", sender, to)
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
		logging.Infof(ctx.Context, "User %q not in any rotations, using a dummy member", auth.CurrentUser(ctx.Context).Email)
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
