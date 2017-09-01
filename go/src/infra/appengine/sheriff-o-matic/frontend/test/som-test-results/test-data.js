let builderOne = {
  builder_name:'builder-1',
  total_failures: 2,
  results: [
    {build_number: 1, actual: [2], expected: [2]},
    {build_number: 2, actual: [1], expected: [2]},
    {build_number: 3, actual: [1], expected: [2]},
  ],
};

let builderTwo = {
  builder_name:'builder-2',
  total_failures: 3,
  results: [
      {build_number: 1, actual: [1], expected: [2]},
    {build_number: 2, actual: [1], expected: [2]},
    {build_number: 3, actual: [1], expected: [2]},
  ],
  };

let builderThree = {
  builder_name:'builder-3',
  total_failures: 1,
  results: [
    {build_number: 1, actual: [2], expected: [2]},
    {build_number: 2, actual: [2], expected: [2]},
    {build_number: 3, actual: [1], expected: [2]},
  ],
};

let masterOne = {
  master_name: 'master-one',
  builder_results: [builderOne, builderTwo],
};

let masterTwo = {
  master_name: 'master-two',
  builder_results: [builderTwo, builderThree],
};

let masterThree = {
  master_name: 'master-three',
  builder_results: [builderOne, builderTwo, builderThree],
};
