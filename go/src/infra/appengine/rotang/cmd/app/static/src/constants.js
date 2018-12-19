// Constants shared between the different elements.
export const timeFormat = 'y-MM-dd HH:mm ZZZZ';
export const durationFormat = 'd days hh hours mm minutes';
export const zone = 'America/Los_Angeles';
export const Shifts = {
  fromAttribute: (value) => {
    let result;
    try {
      result = JSON.parse(value);
    } catch (x) {
      result = value;
      console.warn(`Could not JSON.parse value ${value}`);
    }
    return result;
  },
};
export const BUGLIST = 'https://bugs.chromium.org/p/chromium/issues/list?can=2&q=component%3AInfra%3ESheriffing%3ERotations+&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified&x=m&y=releaseblock&cells=ids';
export const TimeZones = [
  {name: 'America/Los_Angeles', description: 'Mountain View'},
  {name: 'America/New_York', description: 'New York'},
  {name: 'Asia/Tokyo', description: 'Tokyo'},
  {name: 'Australia/Sydney', description: 'Sydney'},
  {name: 'Europe/Paris', description: 'Paris'},
  {name: 'Europe/Stockholm', description: 'Stockholm'},
];
export const BugList = 'https://bugs.chromium.org/p/chromium/issues/list?can=2&q=component%3AInfra%3ESheriffing%3ERotations+&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified&x=m&y=releaseblock&cells=ids';
