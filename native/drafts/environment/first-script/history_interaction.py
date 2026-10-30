import asyncio
import base64
import hashlib
import math
import struct


async def evaluate(session, expression):
    response = await asyncio.wait_for(session.send('Runtime.evaluate', {
        'expression': expression, 'returnByValue': True, 'timeout': 5000}), timeout=8)
    if response.get('exceptionDetails') or 'value' not in response.get('result', {}):
        raise ValueError('Owned restored document evaluation failed')
    return response['result']['value']


async def capture(session, owned):
    before = await evaluate(session, '''(() => {
      const rect = document.querySelector('#probe').getBoundingClientRect();
      return {sample: glintSampleScreen(), clicks: glintTrustedClicks.slice(),
              rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}};
    })()''')
    rect = before['rect']
    if (not isinstance(before['clicks'], list) or set(rect) != {'x', 'y', 'width', 'height'}
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in rect.values())
            or rect['width'] <= 0 or rect['height'] <= 0):
        raise ValueError('Owned restored input geometry or click history is invalid')
    x, y = rect['x'] + rect['width'] / 2, rect['y'] + rect['height'] / 2
    viewport = before['sample']['viewport']
    dpr = before['sample']['screen']['dpr']
    if (set(viewport) != {'width', 'height'}
            or any(type(value) is not int or value <= 0 for value in viewport.values())
            or type(dpr) not in (int, float) or not math.isfinite(dpr) or dpr <= 0):
        raise ValueError('Owned restored viewport or DPR is invalid')
    if not (0 <= x < viewport['width'] and 0 <= y < viewport['height']):
        raise ValueError('Owned restored input target is outside its CSS viewport')
    for kind in ('mousePressed', 'mouseReleased'):
        await asyncio.wait_for(session.send('Input.dispatchMouseEvent', {
            'type': kind, 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}), timeout=8)
    after = await evaluate(session, '({sample: glintSampleScreen(), clicks: glintTrustedClicks.slice()})')
    expected = {'trusted': True, 'x': x, 'y': y, 'inside': True}
    clicks = after.get('clicks')
    input_passed = (isinstance(clicks, list) and len(clicks) == len(before['clicks']) + 1
                    and isinstance(clicks[-1], dict) and clicks[-1].get('trusted') is True
                    and clicks == before['clicks'] + [expected])
    screenshot = await asyncio.wait_for(session.send('Page.captureScreenshot', {
        'format': 'png', 'fromSurface': True, 'captureBeyondViewport': False}), timeout=10)
    png = base64.b64decode(screenshot['data'], validate=True)
    if len(png) < 24 or png[:8] != b'\x89PNG\r\n\x1a\n' or png[12:16] != b'IHDR':
        raise ValueError('Owned restored screenshot is not PNG')
    dimensions = list(struct.unpack('>II', png[16:24]))
    expected_size = [round(viewport[axis] * dpr) for axis in ('width', 'height')]
    (owned / 'history-return-main-cdp.png').write_bytes(png)
    stable = after['sample'] == before['sample']
    return {'passed': input_passed and stable and dimensions == expected_size,
            'scope': 'Main document after actual BFCache restore; no Playwright Frame APIs after restoration',
            'before': before, 'after': after, 'trusted_input_passed': input_passed,
            'screen_stable_across_input': stable, 'screenshot_size': dimensions,
            'expected_screenshot_size': expected_size, 'screenshot_sha256': hashlib.sha256(png).hexdigest(),
            'all_frame_input_verified': False, 'privacy_admitted': False, 'production_admitted': False}
