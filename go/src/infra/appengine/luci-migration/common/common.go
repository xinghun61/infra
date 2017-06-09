package common

import (
	"fmt"
	"time"
)

const (
	day  = 24 * time.Hour
	week = 7 * day
)

// must be sorted by descending.
var units = []struct {
	value  time.Duration
	symbol string
}{
	{week, "w"},
	{day, "d"},
	{time.Hour, "h"},
	{time.Minute, "m"},
	{time.Second, "s"},
	// no need for smaller units
}

// DurationString returns a nice duration string. Supports days and weeks.
func DurationString(d time.Duration) string {
	for _, u := range units {
		if d >= u.value {
			return fmt.Sprintf("%.2f%s", float64(d)/float64(u.value), u.symbol)
		}
	}
	return "0"
}
