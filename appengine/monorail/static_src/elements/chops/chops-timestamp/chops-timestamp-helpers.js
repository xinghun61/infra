// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

export const DEFAULT_DATE_LOCALE = 'en-US';

export function standardTime(date, locale, timezone) {
  if (!date) return;
  locale = locale || DEFAULT_DATE_LOCALE;
  const absoluteTime = date.toLocaleString(locale, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
    timeZone: timezone,
  });
  const timeAgo = relativeTime(date);
  const timeAgoBit = timeAgo ? ` (${timeAgo})` : '';
  return `${absoluteTime}${timeAgoBit}`;
}

export function standardTimeShort(date, locale, timezone) {
  if (!date) return;
  locale = locale || DEFAULT_DATE_LOCALE;
  // For a "short" timestamp, display relative time or a short absolute time
  // if it's been a long time.
  const timeAgo = relativeTime(date);
  if (timeAgo) return timeAgo;
  return date.toLocaleString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: timezone,
  });
}

export function relativeTime(date) {
  if (!date) return;

  const now = new Date();
  let secondDiff = Math.floor((now.getTime() - date.getTime()) / 1000);

  // Use different wording depending on whether the time is in the
  // future or past.
  const pastOrPresentSuffix = secondDiff < 0 ? 'from now' : 'ago';

  secondDiff = Math.abs(secondDiff);
  const minuteDiff = Math.floor(secondDiff / 60);
  const hourDiff = Math.floor(minuteDiff / 60);
  const dayDiff = Math.floor(hourDiff / 24);

  if (!minuteDiff) {
    // Less than a minute.
    return 'just now';
  } else if (!hourDiff) {
    // Less than an hour.
    if (minuteDiff === 1) {
      return `a minute ${pastOrPresentSuffix}`;
    }
    return `${minuteDiff} minutes ${pastOrPresentSuffix}`;
  } else if (!dayDiff) {
    // Less than an day.
    if (hourDiff === 1) {
      return `an hour ${pastOrPresentSuffix}`;
    }
    return `${hourDiff} hours ${pastOrPresentSuffix}`;
  } else if (dayDiff < 30) {
    // Less than a month.
    if (dayDiff === 1) {
      return `a day ${pastOrPresentSuffix}`;
    }
    return `${dayDiff} days ${pastOrPresentSuffix}`;
  }

  // Don't show relative time if it's been a long time ago.
  return '';
}
