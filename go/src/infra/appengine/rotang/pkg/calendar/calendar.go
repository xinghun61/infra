package calendar

import (
	"infra/appengine/rotang"
	"strings"
	"time"

	"go.chromium.org/luci/server/router"
	"golang.org/x/oauth2"

	"google.golang.org/appengine"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	gcal "google.golang.org/api/calendar/v3"
)

// Calendar implements the rotang.Calenderer interface.
type Calendar struct {
	oauthConfig *oauth2.Config
	token       *oauth2.Token
}

var _ rotang.Calenderer = &Calendar{}

// New creates a new Calendar.
func New(oc *oauth2.Config, token *oauth2.Token) *Calendar {
	return &Calendar{
		oauthConfig: oc,
		token:       token,
	}
}

// CreateEvent creates new calendar events from the provided ShiftEntries.
func (c *Calendar) CreateEvent(ctx *router.Context, cfg *rotang.Configuration, shifts []rotang.ShiftEntry) error {
	if err := ctx.Context.Err(); err != nil {
		return err
	}
	return status.Errorf(codes.Unimplemented, "to be implemented")
}

// Event returns the information about the provided shift from the associated calendar event.
func (c *Calendar) Event(ctx *router.Context, cfg *rotang.Configuration, shift *rotang.ShiftEntry) (*rotang.ShiftEntry, error) {
	if err := ctx.Context.Err(); err != nil {
		return nil, err
	}

	return nil, status.Errorf(codes.Unimplemented, "to be implemented")
}

// Events returns events from the specified time range.
func (c *Calendar) Events(ctx *router.Context, cfg *rotang.Configuration, from, to time.Time) ([]rotang.ShiftEntry, error) {
	if err := ctx.Context.Err(); err != nil {
		return nil, err
	}
	cal, err := gcal.New(c.oauthConfig.Client(appengine.NewContext(ctx.Request), c.token))
	if err != nil {
		return nil, err
	}

	events, err := cal.Events.List(cfg.Config.Calendar).
		ShowDeleted(false).SingleEvents(true).
		TimeMin(from.Format(time.RFC3339)).TimeMax(to.Format(time.RFC3339)).
		Q(cfg.Config.Name).
		OrderBy("startTime").Do()
	if err != nil {
		return nil, err
	}
	return eventsToShifts(events, cfg.Config.Name, &cfg.Config.Shifts)
}

// nameShiftSeparator is used to separate the ShiftName from the rota name in Calendar Events.
const nameShiftSeparator = " - "

func eventsToShifts(events *gcal.Events, name string, shifts *rotang.ShiftConfig) ([]rotang.ShiftEntry, error) {
	if events == nil || shifts == nil || name == "" {
		return nil, status.Errorf(codes.InvalidArgument, "all arguments must be set")
	}
	var res []rotang.ShiftEntry
	if len(shifts.Shifts) == 0 {
		return nil, status.Errorf(codes.InvalidArgument, "no shifts")
	}
	for _, e := range events.Items {
		shift := shifts.Shifts[0].Name
		nm := strings.Split(e.Summary, nameShiftSeparator)
		if len(nm) > 1 {
			shift = nm[len(nm)-1]
		}
		start, err := calToTime(e.Start)
		if err != nil {
			return nil, err
		}
		end, err := calToTime(e.End)
		if err != nil {
			return nil, err
		}
		var members []rotang.ShiftMember
		for _, a := range e.Attendees {
			if a.ResponseStatus == "declined" {
				continue
			}
			members = append(members, rotang.ShiftMember{
				Email:     a.Email,
				ShiftName: shift,
			})
		}
		res = append(res, rotang.ShiftEntry{
			Name:      shift,
			StartTime: start,
			EndTime:   end,
			OnCall:    members,
			Comment:   "Generated from calendar event",
		})
	}
	return res, nil
}

const dayFormat = "2006-01-02"

func calToTime(calTime *gcal.EventDateTime) (time.Time, error) {
	tz := time.UTC
	if calTime.TimeZone != "" {
		var err error
		tz, err = time.LoadLocation(calTime.TimeZone)
		if err != nil {
			return time.Time{}, err
		}
	}
	if calTime.Date != "" {
		return time.ParseInLocation(dayFormat, calTime.Date, tz)
	}
	return time.Parse(time.RFC3339, calTime.DateTime)
}

// UpdateEvent updates the calendar event with information from the provided updated shift.
func (c *Calendar) UpdateEvent(ctx *router.Context, cft *rotang.Configuration, updated *rotang.ShiftEntry) error {
	if err := ctx.Context.Err(); err != nil {
		return err
	}
	return status.Errorf(codes.Unimplemented, "to be implemented")
}

// DeleteEvent deletes the calendar event matching the provided shift.
func (c *Calendar) DeleteEvent(ctx *router.Context, cfg *rotang.Configuration, shift *rotang.ShiftEntry) error {
	if err := ctx.Context.Err(); err != nil {
		return err
	}
	return status.Errorf(codes.Unimplemented, "to be implemented")
}
