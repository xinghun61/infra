package chromegomalog

import (
	"testing"
)

func TestURL(t *testing.T) {
	testCases := []struct {
		obj    string
		urlstr string
		isErr  bool
	}{
		{
			obj:    "/2014/09/07/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-165439.13840.gz",
			urlstr: "https://chrome-goma-log.storage.googleapis.com/2014/09/07/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-165439.13840.gz",
		},
		{
			obj:    "2014/09/07/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-165439.13840.gz",
			urlstr: "https://chrome-goma-log.storage.googleapis.com/2014/09/07/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-165439.13840.gz",
		},
		{
			obj:    "2014/09/07/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-165439%2E13840.gz",
			urlstr: "https://chrome-goma-log.storage.googleapis.com/2014/09/07/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-165439.13840.gz",
		},
		{
			obj:   "2014/09/07/build48-m1/ninja_log.build48-m1.chrome-bot.20140907-165439%.13840%gz",
			isErr: true,
		},
	}
	for i, tc := range testCases {
		u, err := URL(tc.obj)
		if tc.isErr {
			if err == nil {
				t.Errorf("%d: URL(%q)=%v, <nil>; want=_, error", i, tc.obj, u)
			}
			continue
		}
		if err != nil {
			t.Errorf("%d: URL(%q)=%v, %v; want=_, <nil>", i, tc.obj, u, err)
			continue
		}
		if u.String() != tc.urlstr {
			t.Errorf("%d: URL(%q)=%q, %v; want=%q, <nil>", i, tc.obj, u, err, tc.urlstr)
		}
	}
}
