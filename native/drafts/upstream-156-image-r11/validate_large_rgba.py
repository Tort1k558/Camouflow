import re


def validate(observed):
    if (not isinstance(observed,dict) or type(observed.get('schema')) is not int or observed['schema'] != 1
            or any(type(observed.get(name)) is not int or observed[name] != value for name,value in
                   (('width',4096),('height',4096),('byteLength',67108864),('opaqueAlphaPixels',16777216)))
            or observed.get('api') != 'webgl2' or observed.get('alpha') is not False):
        raise ValueError('The exact large opaque RGBA8 fixture is required')
    if (type(observed.get('fixtureChangedChannels')) is not int or not 1 <= observed['fixtureChangedChannels'] <= 256
            or not isinstance(observed.get('directSha256'),str)
            or not re.fullmatch('[0-9a-f]{64}',observed['directSha256'])):
        raise ValueError('Active protected direct readback is required')
    expected = [(name,frequent) for name in ('drawImage','png','transferToImageBitmap') for frequent in (False,True)]
    copies = observed.get('copies')
    if (not isinstance(copies,list) or len(copies) != 6 or not all(isinstance(copy,dict) for copy in copies) or
            [(copy.get('name'),copy.get('willReadFrequently')) for copy in copies] != expected):
        raise ValueError('Every full-size copy/backing request is required')
    for copy in copies:
        if type(copy.get('willReadFrequently')) is not bool or type(copy.get('passed')) is not bool:
            raise ValueError('Copy modes and verdicts must be explicit')
        if 'error' in copy:
            if copy['passed'] or not isinstance(copy['error'],str) or not copy['error']:
                raise ValueError('Malformed copy error')
        elif (not isinstance(copy.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',copy['sha256']) or
              copy['passed'] != (copy['sha256'] == observed['directSha256'])):
            raise ValueError('Full-image digest contradicts its copy verdict')
    after = observed.get('afterTransfer')
    restored = (isinstance(after,dict) and isinstance(after.get('pixel'),list)
                and all(type(byte) is int for byte in after['pixel']) and after['pixel'] == [0,0,0,255]
                and type(after.get('error')) is int and after['error'] == 0 and after.get('lost') is False)
    passed = all(copy['passed'] for copy in copies) and restored and 'error' not in observed
    if type(observed.get('passed')) is not bool or observed['passed'] != passed:
        raise ValueError('Large-image aggregate verdict contradicts its observations')
    return dict(passed=passed,measurement_complete=True,full_image_copies=6,rgba8_bytes=67108864)
