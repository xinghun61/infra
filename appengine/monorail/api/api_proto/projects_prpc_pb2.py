# Generated by the pRPC protocol buffer compiler plugin.  DO NOT EDIT!
# source: api/api_proto/projects.proto

import base64
import zlib

from google.protobuf import descriptor_pb2

# Includes description of the api/api_proto/projects.proto and all of its transitive
# dependencies. Includes source code info.
FILE_DESCRIPTOR_SET = descriptor_pb2.FileDescriptorSet()
FILE_DESCRIPTOR_SET.ParseFromString(zlib.decompress(base64.b64decode(
    'eJzdWltvG0ty9nDIIdmU5NboasqXMW3Zli1Rtix7d20f27qdrOWLfCjpHBsIjjAih9KsedsZ0n'
    'uUhyD5AwEWyY/Ic97ztL8gzwvkMb8gjwmQqurL9IiWZSyQl4UhY/qb7uqq6uqeqq/J/sNll/1e'
    'uAx/B72o2+8uw/+/C+r9uEpNt9DudrqRH7bK5XS/ercNr0Sv8o0vyjjoHhqiKj+wiTdh3H8vJ6'
    'gFvx8Ecd+dY8WefxQcxOHfBbOWZ93J1QoI7ELbvcIYvex3PwWd2Qy8Ldao+x4ClTabTIuMe91O'
    'HLhLrKDsAJH2ndLKeFUZUpW9a7qLe4td7AS/9A+GphpF+L2ers743wT9jW6nGR4p9RdZrh/5da'
    'F6aWU6mUf22MO3NdHJvc5GlHM6fjuQ05Qk9g6gSofN4SSDuN9tvw+idhjHIRj1/zbfS3b5y/NJ'
    'X3qs1EtgcidKSKCVf8ywgloCd4eNmEviXkkU/MLql6+e9VrMXrngPmVF7XS3nHQ/vRJlnrwTL2'
    'DwEZv8knHufFrOGc4u3zqvm9Jy+x9GWIHn+AV+n1vsv6zCCDXclT9b3ka3dxKFR8d9b+X+g197'
    'e8eBt3EcddvhoO2tDfrH3SiuemutlkedYi8K4iD6HDSqzNuPA6/b9PrHYezF3UFUD7x6txF40D'
    'zqfg6ioOEdnni+t767uRT3T1oB81phPQCVYIzf9+p+xzsMvGZ30Gl4YQfAwHvzamPr3e6W1wxb'
    'IDzy/D7zjvv9XvxkebkRfA5aXVjbuHrU7R61gips82UAOkti+mUpPl4+jBuMFQoZXoB/HB7twg'
    'XOeJ7foGeLl+B5kY0UHMDH0BfgGGrBuzEaM0atDLy/yDN8m3HVhh4XucNdA8kAMslvG4gNyAr/'
    'XkuxOAcpj3UPixCHXzSQDCDj/LqB2IAs8hUtJQPvM/xQ90C54yClbCDY5zL/lYHYgKzzn8G+LF'
    'gzBdbOkrVZsmUKrJ2DGbLS2mmYYZq5ql3IEjLFr4BEheUIyxuIBUiBjxuIDcgkn9KSLT4DY2a1'
    'ZAskIzINs3GN5QgrGAiOK/IJA7EBmeYzZIHF58Ceq9Iei9oFfplmtcieyyDPo9GWtAcRZiAOIC'
    'VaT4VYgEyAVxLEBuQqv6blWvwKSLlC1ljSGkQuG3OhNVe0NZa05gpYM2sgNiBzoPE8IBleAWvm'
    'uVWe8d7B4e75n2F3+4ewF/r+0RPvISMzcfoKmDlL6mTIzBsw0SVSJyPNRKRCoaEwh7AxA7EAgd'
    'A1EBuQGUOyxW/CmLKWjIYicgNm4xrLEVYwEBxXhOVPEBuQWRiFhtr8Dhh67zxDcafeAUNvkDo2'
    'GbqgDbWloYjc4fM0lS0NXdCG2tLQBW2oLQ1d0IbaZOhdbagtDUVkQRpqS0PvakNtaehdbagtDb'
    '2rDc3yqjh2zzB0RRiKgVwFQ2+SOlkydBnXj8RmpaHLOnCzchsuQ+COG4gFiCu3alaaucw9fv3Q'
    'oTTnIftfj30lV0oyqsrfsxHzm+1Owqedkg+LvtKi4U4zJwr8uKtyEtnC1CgSow/CxqwtUiOJvG'
    'rgl7+P7/x6HU7//mxWfPkRWxNQZY2NbHTb8AULOv1a0HRdlu35/WM5PT3jLGF80AiiEL5IpEGh'
    'VgzjTQFU/sAK34dBq4HDoWsTn0WmIYQUCcE8w73Nsv2TnkhBxlYmki8rCdiDVzXq4N5go34PfP'
    'XZbwlRwrYRBVLW8oIV3viHQQsnBr+18Fn5jRrnae6z4m7f7w9ilAA+jqkhRcgWymgHfic+wE+g'
    'kkHIDgCnprBPT/FbVngVx4MAZzidiFlDiZh7iRVa3ToYHQp1R2t5ar9qVBosD6lAhIJmWH4Aj9'
    'gJZWRrDjbFgjfCuNfyT1KpnsRohq/re/ePFivqxXBLLP9u52Dv4/stfsEdZcWtd/tvRdNyIdl5'
    '9W5PtDLY2t2riZaNXfd3t2Qzi83Ntb0t0cxhc31n541oOjh0vyZbeXecja69f1/b+XFNQoXtfy'
    '1DXjUCG3wfPkD/Y0NeNfLXn1et/HMGzAFlSFYjaIadABRt+2AMHSKHg2YsNPEj0LpTbw0aoLMf'
    'ez0/AlO7Tea1B61+2IPxaDVIj1Gpu+mazHu/HlcZ8yoQWRVPvgJXdPo+WBV0uoOjYxDf7EZtvw'
    '8ZL1gMhnn7rzwYKyOLgQfbAbiyc4QougIjctHz0TcNOFvC5gm+RDnQV+iN3eqtEN6iM5knDy6v'
    '3SWDoGcTlpK60apFVZFtisxxnvIsFyKhfOa5/4jpBMyFQZPsvk7AJuCUn6h43ofd2vcenbLJbL'
    '/de/vGw0IQJjRTNBzjGokUfhsmUokUzjQBH6qxVIo2Aamhy7Z0ijYJYyYrj7ydHjrUb2nLe4Oo'
    '14UAI02ka9DdjeBwcHQEDjQUwi8nCppIZW05wtKZ3SQodDGV2U2CGRNsXSKYd0LOWFlJFBJzL8'
    'WDXg+eGl7cj3D5UBdYTvhe9INO/cTQJgPaoJRJ+fUXWI6wgoFgJmzmmZg3T1Ge+RuJ2JT1lisL'
    '3lb1qLro3cbP1cvgF7/dE3vmNu422E0HOiiUErZOo2f1BLZMowsGgmm0SiYEgpOqZMKCFPQCv3'
    '5e1mRRRwyqJAu+hgGis1UMGUSuypCxZMhcS2WrGDLXQJ3RVB58DasUIw/2dL2g8mBErhn5NK49'
    'Yk4qD/agAhtP5cEe1QvzhVwBc2BMgM4y9DdoaI4UnIdSdgzUycndc0smfjkd9YgUDSQDyAgYpc'
    'ZY/Db04LqHJZGSgWQAGYNQVWMw4cxQ6OZ0+NyR2ZlCsM+ooZtNSWkyxqak1BwD6SMg5hiRgia6'
    'ZWWaWjKQDCCmbjnIq80xORhzLzUmB2PupcY4UGaaYxwYs5ga48CYxdSYPF9K2ZOHMUspe/IwZi'
    'llTwGy3AxtRNmmvNeUgsdolQ4BURA9hED41ZmBsJoURA9l1a4KolVdbaqCCJGHMi4zMuJXU2UL'
    'hsuqPgVUQbRKp0BSED3CjZwqiBBZlVtbYA5hpVRB9AjCjqcKokdwRk5qyRn+GMbMacm4/Ig8Ms'
    'ooXN7HKZ1Ro8eg87SB2IBcglpGlFpPwYXPv6XUeqpdKEqtZ3iIp0otRJ5KF9rShc9SBRG68Jn+'
    'zqhS6xl9Z5JS6zt9aKhSC5Fn0vGq1PpOHxqq1PpOHxqq1PpOHhpYaq2Dod+fFyu4hdaJq0hKrQ'
    '0KStcotRBZl+qoYmtDG6qKrQ39/VLF1gaFrpJs8U1taFYaisiG/BZlpaGb2tCsNHRTG5qVhm5q'
    'NoVWmW+lJGOsILIp4yArY2UrJRk12kpJxljZ0i7M8W1w4dvzYgVPlG0dKzly4WtdPOekCxHZlr'
    'GSky58rV2Yky58rb93OenC1/S9U5It/kYbmpMuROS1ZDZy0oVvUpItGleUhuakC99oQx3+g8ja'
    'vx4reAz+AIZeJHUcMrSmd78jDUXkBzmVIw2taXUcaWgN1OEGYgOCu39NIhbfpezigRe0QZdFTI'
    'i7h3F9gPl+K/wUeBXMXDvVatXMOSoyy3Ckb1BITXrUkb7ZTSlj0VTFVB8bEOV1h8JrT3vdkeGF'
    'yK70uiPDa0+HlyPDa0+HlyPDaw+9rvmHP6+wb7mP+barncpHlpekPPIDRu1Kz+4sy8eDdtuPTm'
    'TBqZp4b9AI4noUUl4pi3gTqvyLpWrwzb+8BgelIr/zieSP1ujZvcyKjW5d5K2S+EgA9ypjjaAX'
    'BXW/D1VwjgQaSCWS1MLmmdSCmjNz1pz21+fMDs35R9vgYjbP4GJSU2ROT3GfMb/RDjsHUdCMQY'
    'NTt16SP6gVqRM8xe5dlq/XRffsWd2dep36nuM0jIN6FNBLB17ma6rprrASPXYjnGo2T9dWX5iJ'
    'yV5IckDR3+42wiaUH7MFEqfb7iobkc9CYPEsgSXVDSU+YIzWTpjLyFzXuHuSXFKt2JJPceXfM5'
    'LcwvVYZoLKoinF1Zt7isLC4YWmYsNus4s+FlB1PPIONPNVrI0lMPEs11gpjA+wCgwjzcqwkO6g'
    'EEFeCDp0wvpxICMnH8bvsOnOszF4RZX+Z7810CszGsZvEzAdOM7XAyf/DYFzk6btHftxcEAG0y'
    'IVaiNh/B5BckflnyxWWpOc3V/kwseKCBQrHYMDz9BtRPUj9fAkGUB5eCL3oWxV/mQzR94jfgMd'
    't8pK4gQ6aCRzG7SlPrlqLFaPsbvFJkUrgAOr2QTN20F0FMj9ODQclXfVgB3s/xa7J+HaSHbn6X'
    'Dd1OFKM/+azQa/1FuDOPwcHIjBsDub4S9BDFGBl7bT+j2Nfy/fut+xsbo6e8SEDk04bV6oJmdT'
    'bbRutGLUVaxrI4mf0wtLujblU+w+MSheGlWgUVPJKCNwEuYXx27/902GV44X+M/cYv+ZKYxQ46'
    '+dEfz8BUIwoQKJm0GqOSbWLQpaePR6h7DY0DFmitpb9ALiVWglPDodAMPvPSxmLCg7v9/368cE'
    'SM6NGTe8I3TDK/g3Dn6fPC/Bu0DXsCrBEwzCuKZKFLuGCE9dbuYIS7Nr45oqUezauKZKBM/g6t'
    'RR0WSIjMscWdFk7hBN5urUUdFkri4cBRsxoS/FFOUlGMGEScoMMYIZyQiatBgygngpJtimWXG1'
    'eoYLHyds06yupwTbdEnXU4ptQmRW1lOKbbo0xDZd0vWUYpsu6XpKsE3lIbYJkUvSCMU2lYfYpv'
    'IQ21TW9ZRFLpxLMWToQkTKBkOGLpxL6Zyh+2aTIUMXzqUYMpvum2e0ZFveQM8ZDBlSgZdTkm26'
    'gy6m+qCkKdBHSRY3zok3svoOekaPyso7aMdA8A7a9EaW7qBVaSTuoG+fx1yrO2iTcrmh+YL0HX'
    'SacrkxRLnc0HxBcget+ILkDtr9wh10QtScfQc9euoOWi2OoFzm9eIoygWRm4bOuOzzQ5TLvF4c'
    'RbnM68UR7Vt6cTJy2RGZl4uTkct+Sy9ORi77Lb04Gbnst2hxbtFC3YPFeQyLM/vFxXnwIGFz7m'
    'kKWLA5i9qHis1B5J4McMXmLA6xOYvah4rNWdQ+FGzOkvahYnMQWTR4IlydpaGL8yXtQ8XmLGkf'
    '2rQ6VX0HbsvVqeo7cIE4gJQMKRliFCfkHbgt16KKd+Bark036dd0Dzt1ty4Qh+7WXQPBu/UJWf'
    '/acmWWYeNc1XKz/H6K18pKZNmYCzfk/RSvhRvyforXwnW+r48nmyLwQUpyDiQjct9YvZzsVTQQ'
    'CxBmSM6B5AcpyQ5f4ebPHhyQjMgDQ7IjexUNxAKEGT97cEDyiuYQEMnzh6m4yINkRFYMH+ZB54'
    'cpyXmicpnh+TxIfpiKiwLRtnNackGTuzN6VAF0Xk1JLhC5ywy7CkTuIlGqJBeJtr2pexQlucsM'
    'BKndksFUFonanYQ4SBCkdq/LVCTLn8Ce3fr6ZYbgJZ/oA1Xwkk/1Z13xkog8kc4RmEOY+bMQJH'
    'JLBsN4gThg9VsXcXQjaXslxUsKavdSipdMqF3FSz7Tv15SvOQz+vXS44LiJZ/jopdveXs7mzt3'
    'fhd1Dw/DTrzwxDPqTcj8GyFW5izFXz4nCjj58QqG/fMh/vI5bBXXQGxAVHBkqf0ixebi5kbkuQ'
    'yOrDx4X6Qk4/Z+AZIvGghKMtncLH+pt0pWbm9EXhi+xu39MiUZ1/UlSJ4yEBsQtVWyZOea3ipZ'
    'ub0ReSm3SlZu77XUeuD2XtNHaFZu77WUNxy+zs2fETlEk5vx4lCfkiHFIYZ8wlgJ3NzrdIT+rU'
    'TyxFmXy2+G1hny9rBB9/GLXvI7XO8o8jt9KOhFGt/p9sMmhgC+6hLhFleTaMhLnnzd0Dw/xJPn'
    'JU8+ZSDIk6vr0hx/9VU2ezVhs1/Bxpsw2OxtvfEUm43IqxRT7RDGUmz2tt54is3e1htPsNnIgM'
    '8brLTgyZmBOICUDN7colET8oeFist+DdnPTS03Q/z3pNY4o1nyZK7MEEuekSz5RQNBlhyDHrMN'
    'wZL/fG62oWjysVM0efkLNLlJgZ9Fk08ZCNLkJjMtaPJ5g7sWnDczEAcQtQ4J4z0lPZgw3sqDCe'
    'NdNZhrwXgzA3EAMeUKvnuKL5ziuxf5kpZr833MVHUPPI72U3Ix19jXXxRHHkb7+oviyMNoH74o'
    'FS03y3/EzEL3yEqEGUgOkJLBxuNR9COs7l0DsQFZAruV3Bz/CbNC3QOPop9ScnOg708gd8ZALE'
    'Bm+S0DsQFZgJmUXId/SPkBD6IPKbkO9TH9gHH1IeUHPIg+kB/+ZEkozz+CmIXKv1lDR9Fe0O4h'
    '1xAvem3/5DDwPgVBD8mPthcHPT+CV1U2NGozaPqDVt/7/SCITui0OorCRnJKDQ2IAuQq6/2lfn'
    'fpU6f7h85wlzr9OP+AWJCDoNOPTg4GUSuxHQ+8jylv5MEbH8Eb0wZiATIjsxNHHncfoVS7o25X'
    '/g/y4VBg')))
_INDEX = {
    f.name: {
      'descriptor': f,
      'services': {s.name: s for s in f.service},
    }
    for f in FILE_DESCRIPTOR_SET.file
}


ProjectsServiceDescription = {
  'file_descriptor_set': FILE_DESCRIPTOR_SET,
  'file_descriptor': _INDEX[u'api/api_proto/projects.proto']['descriptor'],
  'service_descriptor': _INDEX[u'api/api_proto/projects.proto']['services'][u'Projects'],
}
