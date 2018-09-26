package handlers

import (
	"bytes"
	"infra/appengine/rotang"
	"net/http"
	"text/template"
	"time"

	"go.chromium.org/gae/service/mail"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// JobEmail sends emails to upcoming oncallers.
// The rotang.Email `DaysBeforeNotify` number is used to
// set when the mail is going to be sent.
// Setting DaysBeforeNotify == 0 disables sending Emails for that
// rotation.
func (h *State) JobEmail(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	now := clock.Now(ctx.Context)
	configs, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, "")
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}
	for _, cfg := range configs {
		if err := h.notifyEmail(ctx.Context, cfg, now); err != nil {
			logging.Warningf(ctx.Context, "notifyEmail(ctx, _,%v) for rota: %q failed: %v", now, cfg.Config.Name, err)
		}
	}
}

// notifyEmail figures out if a notification should be sent for the specified shift.
func (h *State) notifyEmail(ctx context.Context, cfg *rotang.Configuration, t time.Time) error {
	if cfg.Config.Email.DaysBeforeNotify == 0 || !cfg.Config.Enabled {
		return nil
	}
	t = t.UTC().Add(time.Duration(cfg.Config.Email.DaysBeforeNotify) * 24 * time.Hour)
	ss := cfg.Config.Shifts.StartTime.UTC()
	for _, s := range cfg.Config.Shifts.Shifts {
		// Only care about the date of the `t`time and then use the StartTime from the ShiftConfiguration to set
		// the start of the shift.
		ct := time.Date(t.Year(), t.Month(), t.Day(), ss.Hour(), ss.Minute(), ss.Second(), ss.Nanosecond(), time.UTC)
		shift, err := h.shiftStore(ctx).Oncall(ctx, ct, cfg.Config.Name)
		if err != nil {
			if status.Code(err) == codes.NotFound {
				continue
			}
			return err
		}
		for _, m := range shift.OnCall {
			if err := h.sendMail(ctx, cfg, shift, m.Email); err != nil {
				return err
			}
		}
		ss, t = ss.Add(s.Duration), t.Add(s.Duration)
	}
	return nil
}

// sendMail executes the subject/body templates and sends the mail out.
func (h *State) sendMail(ctx context.Context, cfg *rotang.Configuration, shift *rotang.ShiftEntry, email string) error {
	m, err := h.memberStore(ctx).Member(ctx, email)
	if err != nil {
		return err
	}
	info := rotang.Info{
		RotaName:    cfg.Config.Name,
		ShiftConfig: cfg.Config.Shifts,
		ShiftEntry:  *shift,
		Member:      *m,
	}

	subjectTemplate, err := template.New("Subject").Parse(cfg.Config.Email.Subject)
	if err != nil {
		return err
	}
	bodyTemplate, err := template.New("Body").Parse(cfg.Config.Email.Body)
	if err != nil {
		return err
	}

	var subjectBuf, bodyBuf bytes.Buffer
	if err := subjectTemplate.Execute(&subjectBuf, &info); err != nil {
		return err
	}
	if err := bodyTemplate.Execute(&bodyBuf, &info); err != nil {
		return err
	}

	return h.mailSender.Send(ctx, &mail.Message{
		Sender:  h.mailAddress,
		To:      []string{email},
		Subject: subjectBuf.String(),
		Body:    bodyBuf.String(),
	})
}
