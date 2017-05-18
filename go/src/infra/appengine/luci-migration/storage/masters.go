package storage

// TODO(nodir): move the master list to luci-config.

// Master is a Buildbot master.
type Master struct {
	Name           string
	SchedulingType SchedulingType
	LUCIBucket     string
	Public         bool
	OS             OS
}

var masters = []*Master{
	{
		Name:           "tryserver.chromium.linux",
		SchedulingType: TryScheduling,
		LUCIBucket:     "luci.chromium.try",
		Public:         true,
		OS:             Linux,
	},
	{
		Name:           "tryserver.chromium.win",
		SchedulingType: TryScheduling,
		LUCIBucket:     "luci.chromium.try",
		Public:         true,
		OS:             Windows,
	},
	{
		Name:           "tryserver.chromium.mac",
		SchedulingType: TryScheduling,
		LUCIBucket:     "luci.chromium.try",
		Public:         true,
		OS:             Mac,
	},
}

// GetMasters returns buildbot masters in undefined order.
func GetMasters() []*Master {
	result := make([]*Master, len(masters))
	copy(result, masters)
	return result
}
