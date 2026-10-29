(() => {
  'use strict';
  window.glintSampleScreen = () => ({
    screen: {
      width: screen.width, height: screen.height,
      availWidth: screen.availWidth, availHeight: screen.availHeight,
      availLeft: screen.availLeft, availTop: screen.availTop,
      colorDepth: screen.colorDepth, pixelDepth: screen.pixelDepth,
      dpr: devicePixelRatio,
      orientation: {type: screen.orientation.type, angle: screen.orientation.angle}
    },
    viewport: {width: innerWidth, height: innerHeight},
    media: {
      width: matchMedia(`(device-width: ${screen.width}px)`).matches,
      height: matchMedia(`(device-height: ${screen.height}px)`).matches,
      resolution: matchMedia(`(resolution: ${devicePixelRatio}dppx)`).matches
    }
  });
  window.glintFirstScreen = window.glintSampleScreen();
  window.glintScreenChanges = [];
  window.glintTrustedClicks = [];
  screen.addEventListener('change', () => window.glintScreenChanges.push({
    kind: 'screen', value: window.glintSampleScreen()
  }));
  screen.orientation.addEventListener('change', () => window.glintScreenChanges.push({
    kind: 'orientation', value: window.glintSampleScreen()
  }));
  addEventListener('click', event => {
    if (event.target.id !== 'probe') return;
    const rect = event.target.getBoundingClientRect();
    window.glintTrustedClicks.push({
      trusted: event.isTrusted, x: event.clientX, y: event.clientY,
      inside: event.clientX >= rect.left && event.clientX <= rect.right &&
              event.clientY >= rect.top && event.clientY <= rect.bottom
    });
  });
})();
