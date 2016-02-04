The format for recipe result for compile failures is:

    {
        'report': {
            'result': {
                'rev1': 'passed',
                'rev2': 'failed'
            }
        }
    }


The format for final try-job result for compile failures saved in WfTryJob.compile_results is:

    [
        {
            'report': {
                'result': {
                    'rev1': 'passed',
                    'rev2': 'failed'
                }
            },
            'url': 'url',
            'try_job_id': '1',
            'culprit': {
                'revision': 'rev2',
                'commit_position': '2',
                'review_url': 'url_2'
            }
        },
        ...
    ]


The format for recipe result for test failures is:
TODO(chanli): update the format after the changes on test recipe.

    'result': {
        'rev1': {
            'a_test': {
                'status': 'failed',
                'valid': True,
                'failures': ['a_test1']
            },
            'b_test': {
                'status': 'failed',
                'valid': True,
                'failures': ['b_test1']
            },
            'c_test': {
                'status': 'passed',
                'valid': True
            }
        },
        'rev2': {
            'a_test': {
                'status': 'failed',
                'valid': True,
                'failures': ['a_test1', 'a_test2']
            },
            'b_test': {
                'status': 'passed',
                'valid': True
            },
            'c_test': {
                'status': 'failed',
                'valid': True,
                'failures': []
            }
        }
    }


The format for final try-job result for test failures saved in WfTryJob.test_results is:

    [
        {
            'result': {
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    },
                    'c_test': {
                        'status': 'passed',
                        'valid': True
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1', 'a_test2']
                    },
                    'b_test': {
                        'status': 'passed',
                        'valid': True
                    },
                    'c_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': []
                    }
                }
            },
            'url': 'url',
            'try_job_id': '1',
            'culprit': {
                'a_test': {
                    'tests': {
                        'a_test1': {
                          'revision': 'rev1',
                          'commit_position': '1',
                          'review_url': 'url_1'
                        },
                        'a_test2': {
                          'revision': 'rev2',
                          'commit_position': '2',
                          'review_url': 'url_2'
                        }
                    }
                },
                'b_test': {
                    'tests': {
                        'b_test1': {
                          'revision': 'rev1',
                          'commit_position': '1',
                          'review_url': 'url_1'
                        }
                    }
                },
                'c_test': {
                    'revision': 'rev2',
                    'commit_position': '2',
                    'review_url': 'url_2',
                    'tests': {}
                }
            }
        },
        ...
    }
