async ({mode}) => {
  if (!['baseline', 'legacy', 'math'].includes(mode)) throw new Error('Explicit Audio mode required');
  const rows = [];
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const deadline = (promise) => {
    let timer;
    return Promise.race([
      promise,
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Owned Audio completion deadline')), 5000); }),
    ]).finally(() => clearTimeout(timer));
  };
  const frame = async () => {
    const element = document.createElement('iframe');
    const loaded = new Promise((resolve, reject) => {
      element.onload = resolve;
      element.onerror = () => reject(new Error('Owned iframe failed to load'));
    });
    element.srcdoc = '<!doctype html><meta charset="utf-8"><title>Owned Audio lifecycle</title>';
    document.body.append(element);
    await deadline(loaded);
    return element;
  };
  const graph = (realm, rate, frames) => {
    const context = new realm.OfflineAudioContext(2, frames, rate);
    const input = context.createBuffer(2, frames, rate);
    for (let channel = 0; channel < 2; channel += 1) input.getChannelData(channel).fill(0.25);
    const source = context.createBufferSource();
    source.buffer = input;
    source.connect(context.destination);
    source.start();
    return {context, input};
  };
  const measure = async (identity, run) => {
    try {
      const checks = await run();
      rows.push({...identity, checks, passed: Object.values(checks).every((value) => value === true)});
    } catch (error) {
      rows.push({...identity, passed: false, error: String(error)});
    }
  };

  for (const rate of [44100, 48000]) {
    for (const frames of [128, 4096, 65536]) {
      for (const reenter of [false, true]) {
        await measure({kind: 'event-promise', rate, frames, reenter}, async () => {
          const {context, input} = graph(window, rate, frames);
          let count = 0;
          let eventBuffer;
          let retry;
          context.oncomplete = (event) => {
            count += 1;
            eventBuffer = event.renderedBuffer;
            eventBuffer.getChannelData(0)[0] = 0.375;
            if (reenter) {
              try {
                retry = context.startRendering().then(() => 'unexpected-fulfillment', (error) => error.name);
              } catch (error) {
                retry = Promise.resolve(error.name);
              }
            }
          };
          const buffer = await deadline(context.startRendering());
          const retryError = reenter ? await deadline(retry) : null;
          await sleep(20);
          return {
            oneEvent: count === 1,
            sameMutableBuffer: buffer === eventBuffer && buffer.getChannelData(0)[0] === 0.375,
            closed: context.state === 'closed',
            format: buffer.length === frames && buffer.numberOfChannels === 2 && buffer.sampleRate === rate,
            sourceUnchanged: [...input.getChannelData(0), ...input.getChannelData(1)].every((value) => value === 0.25),
            repeatRejected: !reenter || retryError === 'InvalidStateError',
          };
        });
      }
    }
    for (let repetition = 0; repetition < 3; repetition += 1) {
      await measure({kind: 'detach-pending', rate, repetition}, async () => {
        const element = await frame();
        try {
          const {context} = graph(element.contentWindow, rate, 131072);
          let events = 0;
          let fulfilled = false;
          context.oncomplete = () => { events += 1; };
          context.startRendering().then(() => { fulfilled = true; }, () => {});
          element.remove();
          await sleep(150);
          return {noEventInObservationWindow: events === 0, noFulfillmentInObservationWindow: !fulfilled,
            frameRemoved: !element.isConnected};
        } finally {
          element.remove();
        }
      });
      await measure({kind: 'detach-in-completion', rate, repetition}, async () => {
        const element = await frame();
        try {
          const {context} = graph(element.contentWindow, rate, 4096);
          let events = 0;
          let eventBuffer;
          let promiseBuffer;
          let fulfilled = false;
          const completed = new Promise((resolve) => {
            context.oncomplete = (event) => {
              events += 1;
              eventBuffer = event.renderedBuffer;
              eventBuffer.getChannelData(0)[0] = 0.375;
              element.remove();
              resolve();
            };
          });
          context.startRendering().then((buffer) => { fulfilled = true; promiseBuffer = buffer; }, () => {});
          await deadline(completed);
          await sleep(150);
          return {oneEvent: events === 1, frameRemoved: !element.isConnected,
            retainedMutation: eventBuffer.getChannelData(0)[0] === 0.375,
            fulfilledBufferAgreesIfDelivered: !fulfilled || promiseBuffer === eventBuffer};
        } finally {
          element.remove();
        }
      });
    }
    if (mode === 'legacy') {
      await measure({kind: 'budget-retry', rate}, async () => {
        const context = new OfflineAudioContext(2, 8388609, rate);
        const errors = [];
        for (let attempt = 0; attempt < 3; attempt += 1) {
          try {
            await deadline(context.startRendering());
            errors.push('unexpected-fulfillment');
          } catch (error) {
            errors.push(error.name);
          }
        }
        return {allRejectBeforeRendering: errors.every((name) => name === 'NotReadableError'),
          contextStillSuspended: context.state === 'suspended'};
      });
    }
  }
  return {schema: 1, mode, passed: rows.every((row) => row.passed), rows,
    scope: 'Owned Audio lifecycle only; pending-detach observation window 150ms, not proof of all future scheduling or private-key erasure'};
}
