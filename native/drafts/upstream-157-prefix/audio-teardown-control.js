async () => {
  const frame = document.createElement('iframe');
  frame.src = location.href;
  let completionCount = 0;
  let renderState = 'pending';
  let futureSuspendState = 'pending';
  const bounded = promise => {
    let timer;
    return Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('Audio teardown probe timed out')), 5000);
      })
    ]).finally(() => clearTimeout(timer));
  };
  try {
    await bounded(new Promise((resolve, reject) => {
      frame.onload = resolve;
      frame.onerror = () => reject(new Error('Audio fixture frame failed to load'));
      document.body.append(frame);
    }));
    const context = new frame.contentWindow.OfflineAudioContext(1, 256, 44100);
    const source = context.createConstantSource();
    source.offset.value = 0.25;
    source.connect(context.destination);
    source.start(0);
    context.oncomplete = () => { completionCount += 1; };
    const suspended = context.suspend(0);
    context.suspend(128 / 44100).then(
      () => { futureSuspendState = 'fulfilled'; },
      () => { futureSuspendState = 'rejected'; }
    );
    context.startRendering().then(
      () => { renderState = 'fulfilled'; },
      () => { renderState = 'rejected'; }
    );
    await bounded(suspended);
    const suspendedBeforeDetach = context.state === 'suspended' && context.currentTime === 0;
    const pendingBeforeDetach = renderState === 'pending' && futureSuspendState === 'pending';
    frame.remove();
    let retryError = null;
    try {
      await bounded(context.startRendering());
    } catch (error) {
      retryError = error.name;
    }
    // Observe parent-realm callbacks without waiting on Promises in the dead realm.
    for (let turn = 0; turn < 4; turn += 1) {
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    return {
      suspendedBeforeDetach,
      pendingBeforeDetach,
      frameRemoved: !frame.isConnected,
      renderState,
      futureSuspendState,
      completionCount,
      stateAfterDetach: context.state,
      retryError,
      passed: suspendedBeforeDetach && pendingBeforeDetach && !frame.isConnected &&
        renderState !== 'fulfilled' && futureSuspendState !== 'fulfilled' &&
        completionCount === 0 && retryError === 'InvalidStateError'
    };
  } finally {
    frame.remove();
  }
}
