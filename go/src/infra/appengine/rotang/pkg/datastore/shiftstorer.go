package datastore

import (
	"infra/appengine/rotang"
	"sort"
	"time"

	"context"

	"go.chromium.org/gae/service/datastore"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	shiftEntryKind = "DsShiftEntry"
	shiftKind      = "DsShifts"
)

// DsShifts is the parent entry used for DsShiftEntry.
type DsShifts struct {
	Key  *datastore.Key `gae:"$parent"`
	Name string         `gae:"$id"`
}

// DsShiftEntry represents a single shift entry.
type DsShiftEntry struct {
	Key       *datastore.Key `gae:"$parent"`
	Name      string
	ID        int64 `gae:"$id"`
	StartTime time.Time
	EndTime   time.Time
	OnCall    []rotang.ShiftMember
	EvtID     string
	Comment   string
}

var (
	_ rotang.ShiftStorer = &Store{}
)

// Oncall returns the shift entry for the specific time.
func (s *Store) Oncall(ctx context.Context, at time.Time, rota string) (*rotang.ShiftEntry, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}

	dsShifts := DsShifts{
		Key:  rootKey(ctx),
		Name: rota,
	}
	if err := datastore.Get(ctx, &dsShifts); err != nil {
		if err == datastore.ErrNoSuchEntity {
			return nil, status.Errorf(codes.NotFound, "rota not found")
		}
		return nil, err
	}
	at = at.UTC()
	queryShifts := datastore.NewQuery(shiftEntryKind).Ancestor(datastore.KeyForObj(ctx, &dsShifts)).Gte("EndTime", at)
	var dsEntries []DsShiftEntry
	if err := datastore.GetAll(ctx, queryShifts, &dsEntries); err != nil {
		return nil, err
	}
	for _, shift := range dsEntries {
		if !(at.After(shift.StartTime) || at.Equal(shift.StartTime)) && at.Before(shift.EndTime) {
			continue
		}
		shiftDuration := shift.EndTime.Sub(shift.StartTime) % (24 * time.Hour)
		// Duration == 0  => 24 hour shift.
		if shiftDuration != 0 {
			// RotaNG stores split shifts like:
			//
			// MTV Shift 2018-10-01 07:00 PDT -> 2018-10-05 19:00 PDT 12hours
			// SYD Shift 2018-10-01 19:00 PDT -> 2018-10-06 07:00 PDT 12hours
			//
			// First the `s` time is set to the same day as the requested at time
			// with H and M set to `shift.StartTime` -> 2018-10-04 19:00.
			// `e` is set by adding the Shift Duration to `s`.
			//
			// In this case though at 2018-10-04 05:00 will not be inside the s->e range
			// 2018-10-04 19:00 -> 2018-10-05 07:00 due to the date changing during the
			// shift. To check for this happening the duration between `at` and `e` is
			// calculated. If this is > shiftDuration (12h in this case) the `s` and `e`
			// times are backed up by one day.
			s := time.Date(at.Year(), at.Month(), at.Day(),
				shift.StartTime.Hour(), shift.StartTime.Minute(),
				shift.StartTime.Second(), shift.StartTime.Nanosecond(),
				time.UTC)
			e := s.Add(shiftDuration)
			if e.Sub(at) > shiftDuration {
				s = s.Add(-24 * time.Hour)
				e = e.Add(-24 * time.Hour)
			}
			if !((at.After(s) || at.Equal(s)) && at.Before(e)) {
				continue
			}
		}

		return &rotang.ShiftEntry{
			Name:      shift.Name,
			OnCall:    shift.OnCall,
			StartTime: shift.StartTime,
			EndTime:   shift.EndTime,
			Comment:   shift.Comment,
			EvtID:     shift.EvtID,
		}, nil
	}
	return nil, status.Errorf(codes.NotFound, "no matching shift found for rota: %q", rota)
}

// AddShifts adds shift entries.
func (s *Store) AddShifts(ctx context.Context, rota string, entries []rotang.ShiftEntry) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	dsShifts := &DsShifts{
		Key:  rootKey(ctx),
		Name: rota,
	}
	dsRota := &DsRotaConfig{
		Key: rootKey(ctx),
		ID:  rota,
	}

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		if err := datastore.Get(ctx, dsRota); err != nil {
			return err
		}
		memberSet := make(map[string]struct{})
		for _, m := range dsRota.Members {
			memberSet[m.Email] = struct{}{}
		}

		if err := datastore.Get(ctx, dsShifts); err != nil {
			if err != datastore.ErrNoSuchEntity {
				return err
			}
			if err := datastore.Put(ctx, dsShifts); err != nil {
				return err
			}
		}

		for _, e := range entries {
			if err := datastore.Get(ctx, &DsShiftEntry{
				Key: datastore.NewKey(ctx, shiftKind, rota, 0, datastore.KeyForObj(ctx, dsShifts)),
				ID:  e.StartTime.Unix(),
			}); err == nil {
				return status.Errorf(codes.AlreadyExists, "shift already exists at time: %v", e.StartTime)
			}
			for _, o := range e.OnCall {
				if _, ok := memberSet[o.Email]; !ok {
					return status.Errorf(codes.NotFound, "shift member: %q not a member of rota: %q", o.Email, rota)
				}
			}
			// TODO(olakar): Consider handling overlapping shifts.
			shiftEntry := &DsShiftEntry{
				Key:       datastore.NewKey(ctx, shiftKind, rota, 0, datastore.KeyForObj(ctx, dsShifts)),
				Name:      e.Name,
				ID:        e.StartTime.Unix(),
				StartTime: e.StartTime.UTC(),
				EndTime:   e.EndTime.UTC(),
				Comment:   e.Comment,
				OnCall:    e.OnCall,
				EvtID:     e.EvtID,
			}
			if err := datastore.Put(ctx, shiftEntry); err != nil {
				return err
			}
		}
		return nil
	}, nil)
}

// DeleteShift deletes the identified shift.
func (s *Store) DeleteShift(ctx context.Context, rota string, start time.Time) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	return datastore.Delete(ctx, &DsShiftEntry{
		Key: datastore.NewKey(ctx, shiftKind, rota, 0, datastore.KeyForObj(ctx, &DsShifts{
			Key:  rootKey(ctx),
			Name: rota,
		})),
		ID: start.Unix(),
	})
}

// UpdateShift updates the information in the identified shift.
func (s *Store) UpdateShift(ctx context.Context, rota string, shift *rotang.ShiftEntry) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if shift == nil || rota == "" {
		return status.Errorf(codes.InvalidArgument, "shift and rota must be set")
	}

	return datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		key := datastore.NewKey(ctx, shiftKind, rota, 0, datastore.KeyForObj(ctx, &DsShifts{
			Key:  rootKey(ctx),
			Name: rota,
		}))
		if err := datastore.Get(ctx, &DsShiftEntry{
			Key: key,
			ID:  shift.StartTime.Unix(),
		}); err != nil {
			if err == datastore.ErrNoSuchEntity {
				return status.Errorf(codes.NotFound, "shift not found")
			}
			return err
		}
		return datastore.Put(ctx, &DsShiftEntry{
			Key:       key,
			Name:      shift.Name,
			ID:        shift.StartTime.Unix(),
			StartTime: shift.StartTime.UTC(),
			EndTime:   shift.EndTime.UTC(),
			Comment:   shift.Comment,
			OnCall:    shift.OnCall,
			EvtID:     shift.EvtID,
		})
	}, nil)
}

type byStartTime []rotang.ShiftEntry

func (s byStartTime) Less(i, j int) bool {
	return s[i].StartTime.Before(s[j].StartTime)
}

func (s byStartTime) Len() int {
	return len(s)
}

func (s byStartTime) Swap(i, j int) {
	s[i], s[j] = s[j], s[i]
}

// AllShifts fetches all shifts from a rotation rota ordered by StartTime.
func (s *Store) AllShifts(ctx context.Context, rota string) ([]rotang.ShiftEntry, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	dsShifts := DsShifts{
		Key:  rootKey(ctx),
		Name: rota,
	}
	if err := datastore.Get(ctx, &dsShifts); err != nil {
		if err == datastore.ErrNoSuchEntity {
			return nil, status.Errorf(codes.NotFound, "shifts not found")
		}
		return nil, err
	}
	queryShifts := datastore.NewQuery(shiftEntryKind).Ancestor(datastore.KeyForObj(ctx, &DsShifts{
		Key:  rootKey(ctx),
		Name: rota,
	}))
	var dsEntries []DsShiftEntry
	if err := datastore.GetAll(ctx, queryShifts, &dsEntries); err != nil {
		return nil, err
	}

	var shifts []rotang.ShiftEntry
	for _, shift := range dsEntries {
		shifts = append(shifts, rotang.ShiftEntry{
			Name:      shift.Name,
			StartTime: shift.StartTime,
			EndTime:   shift.EndTime,
			Comment:   shift.Comment,
			OnCall:    shift.OnCall,
			EvtID:     shift.EvtID,
		})
	}

	// TODO(olakar): Look into why the Store emulator doesn't generated indexes automatically when
	// specifing .Order for the queryShifts query.
	sort.Sort(byStartTime(shifts))

	return shifts, nil
}

// ShiftsFromTo fetches shifts inside the specified range.
// Leaving From or To to time.Unset gives either from the beginning of time or end of time.
func (s *Store) ShiftsFromTo(ctx context.Context, rota string, from, to time.Time) ([]rotang.ShiftEntry, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	from, to = from.UTC(), to.UTC()
	dsShifts := DsShifts{
		Key:  rootKey(ctx),
		Name: rota,
	}
	if err := datastore.Get(ctx, &dsShifts); err != nil {
		if err == datastore.ErrNoSuchEntity {
			return nil, status.Errorf(codes.NotFound, "shifts not found")
		}
		return nil, err
	}

	query := datastore.NewQuery(shiftEntryKind).Ancestor(datastore.KeyForObj(ctx, &dsShifts))

	var dsEntries []DsShiftEntry
	switch {
	case to.IsZero() && from.IsZero():
		return s.AllShifts(ctx, rota)
	case from.IsZero():
		if err := datastore.GetAll(ctx, query.Lt("StartTime", to), &dsEntries); err != nil {
			return nil, err
		}
	case to.IsZero():
		if err := datastore.GetAll(ctx, query.Gte("EndTime", from), &dsEntries); err != nil {
			return nil, err
		}
	default:
		// Only a single inequality filter allowed for Datastore queries.
		// https://cloud.google.com/appengine/docs/standard/go/datastore/query-restrictions
		// To work around this the From time is queried with datastore and to is filtered
		// out manually.
		var tmpEntries []DsShiftEntry
		if err := datastore.GetAll(ctx, query.Gte("EndTime", from), &tmpEntries); err != nil {
			return nil, err
		}
		sort.Slice(dsEntries, func(i, j int) bool {
			return dsEntries[i].StartTime.Before(dsEntries[j].StartTime)
		})
		for _, e := range tmpEntries {
			if e.StartTime.After(to) && e.EndTime.After(to) {
				continue
			}
			dsEntries = append(dsEntries, e)
		}

	}

	var shifts []rotang.ShiftEntry
	for _, shift := range dsEntries {
		shifts = append(shifts, rotang.ShiftEntry{
			Name:      shift.Name,
			StartTime: shift.StartTime,
			EndTime:   shift.EndTime,
			Comment:   shift.Comment,
			OnCall:    shift.OnCall,
			EvtID:     shift.EvtID,
		})
	}

	return shifts, nil
}

// Shift returns the requested shift.
func (s *Store) Shift(ctx context.Context, rota string, start time.Time) (*rotang.ShiftEntry, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	entry := DsShiftEntry{
		Key: datastore.NewKey(ctx, shiftKind, rota, 0, datastore.KeyForObj(ctx, &DsShifts{
			Key:  rootKey(ctx),
			Name: rota,
		})),
		ID: start.Unix(),
	}
	if err := datastore.Get(ctx, &entry); err != nil {
		return nil, err
	}
	return &rotang.ShiftEntry{
		Name:      entry.Name,
		StartTime: entry.StartTime,
		EndTime:   entry.EndTime,
		Comment:   entry.Comment,
		OnCall:    entry.OnCall,
		EvtID:     entry.EvtID,
	}, nil
}

// DeleteAllShifts deletes all shifts from the specified rota.
func (s *Store) DeleteAllShifts(ctx context.Context, rota string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	shiftKey := datastore.KeyForObj(ctx, &DsShifts{
		Key:  rootKey(ctx),
		Name: rota,
	})
	var shifts []DsShiftEntry
	if err := datastore.GetAll(ctx, datastore.NewQuery(shiftEntryKind).Ancestor(shiftKey), &shifts); err != nil {
		return err
	}

	return datastore.Delete(ctx, shifts, &DsShifts{
		Key:  rootKey(ctx),
		Name: rota,
	})
}
