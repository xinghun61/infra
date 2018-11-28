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
