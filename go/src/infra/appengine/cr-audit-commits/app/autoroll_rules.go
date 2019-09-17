// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"strings"
)

const (
	dirLayoutTests = "third_party/blink/web_tests"
	dirSkiaAPIDocs = "site/user/api"

	fileAFDO            = "chrome/android/profiles/newest.txt"
	fileDEPS            = "DEPS"
	fileFreeTypeConfigH = "third_party/freetype/include/freetype-custom-config/ftconfig.h"
	fileFreeTypeOptionH = "third_party/freetype/include/freetype-custom-config/ftoption.h"
	fileFreeTypeReadme  = "third_party/freetype/README.chromium"
	fileFuchsiaSDKLinux = "build/fuchsia/linux.sdk.sha1"
	fileFuchsiaSDKMac   = "build/fuchsia/mac.sdk.sha1"
	fileGoMod           = "go.mod"
	fileGoSum           = "go.sum"
	fileOrderfile       = "chromeos/profiles/orderfile.newest.txt"
	fileSkiaManifest    = "manifest/skia"
	fileSkiaTasks       = "infra/bots/tasks.json"

	tmplSkiaAsset = "infra/bots/assets/%s/VERSION"
)

var (
	dirsSKCMS = []string{"include/third_party/skcms", "third_party/skcms"}
)

// SkiaAsset returns the path to the named Skia asset version file.
func SkiaAsset(asset string) string {
	return fmt.Sprintf(tmplSkiaAsset, asset)
}

// AutoRollRulesForFilesAndDirs returns an AccountRules instance for an account
// which should only modify the given set of files and directories.
func AutoRollRulesForFilesAndDirs(account string, files, dirs []string) AccountRules {
	return AccountRules{
		Account: account,
		Rules: []Rule{
			OnlyModifiesFilesAndDirsRule{
				name:  fmt.Sprintf("OnlyModifies_%s", strings.Join(append(files, dirs...), "+")),
				files: files,
				dirs:  dirs,
			},
		},
		notificationFunction: fileBugForAutoRollViolation,
	}
}

// AutoRollRulesForDirList returns an AccountRules instance for an account
// which should only modify the given set of directories.
func AutoRollRulesForDirList(account string, dirs []string) AccountRules {
	return AutoRollRulesForFilesAndDirs(account, []string{}, dirs)
}

// AutoRollRulesForFileList returns an AccountRules instance for an account
// which should only modify the given set of files.
func AutoRollRulesForFileList(account string, files []string) AccountRules {
	return AutoRollRulesForFilesAndDirs(account, files, []string{})
}

// AutoRollRulesDEPS returns an AccountRules instance for an account which should
// only modify the ``DEPS`` file.
func AutoRollRulesDEPS(account string) AccountRules {
	return AutoRollRulesForFileList(account, []string{fileDEPS})
}

// AutoRollRulesDEPSAndTasks returns an AccountRules instance for an account
// which should only modify the ``DEPS`` and ``infra/bots/tasks.json`` files.
// The ``go.mod`` and ``go.sum`` files may also be updated in the process.
func AutoRollRulesDEPSAndTasks(account string) AccountRules {
	return AutoRollRulesForFileList(account, []string{fileDEPS, fileGoMod, fileGoSum, fileSkiaTasks})
}

// AutoRollRulesFuchsiaSDKVersion returns an AccountRules instance for an
// account which should only modifiy ``build/fuchsia/sdk.sha1``.
func AutoRollRulesFuchsiaSDKVersion(account string) AccountRules {
	return AutoRollRulesForFileList(account, []string{fileFuchsiaSDKLinux, fileFuchsiaSDKMac})
}

// AutoRollRulesSKCMS returns an AccountRules instance for an account which
// should only modify ``third_party/skcms``.
func AutoRollRulesSKCMS(account string) AccountRules {
	return AutoRollRulesForDirList(account, dirsSKCMS)
}

// AutoRollRulesLayoutTests returns an AccountRules instance for an account
// which should only modify ``third_party/blink/web_tests``.
func AutoRollRulesLayoutTests(account string) AccountRules {
	return AutoRollRulesForDirList(account, []string{dirLayoutTests})
}

// AutoRollRulesAPIDocs returns an AccountRules instance for an account which
// should only modify ``site/user/api``.
func AutoRollRulesAPIDocs(account string) AccountRules {
	return AutoRollRulesForDirList(account, []string{dirSkiaAPIDocs})
}

// AutoRollRulesSkiaManifest returns an AccountRules instance for an account
// which should only modify ``manifest/skia``.
func AutoRollRulesSkiaManifest(account string) AccountRules {
	return AutoRollRulesForFileList(account, []string{fileSkiaManifest})
}
