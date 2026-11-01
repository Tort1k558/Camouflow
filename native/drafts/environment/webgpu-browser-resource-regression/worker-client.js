async ({kind}) => {
  const nonce = crypto.randomUUID();
  const worker = new Worker('/bound-worker.js');
  let timeout;
  try {
    return await new Promise((resolve, reject) => {
      timeout = setTimeout(() => reject(new Error('Owned bound worker timeout')), 85000);
      worker.onerror = event => reject(new Error(event.message));
      worker.onmessage = ({data}) => {
        if (!data || data.nonce !== nonce || !data.realm || !data.realm.secure
            || !data.realm.dedicated || data.realm.origin !== location.origin
            || data.realm.url !== new URL('/bound-worker.js', location.href).href) {
          reject(new Error('Owned worker realm/nonce mismatch')); return;
        }
        if (data.error) { reject(new Error(data.error)); return; }
        if (kind === 'nested' && (!data.nestedRealm || !data.nestedRealm.secure
            || !data.nestedRealm.dedicated || data.nestedRealm.origin !== location.origin
            || data.nestedRealm.url !== new URL('/bound-worker.js', location.href).href)) {
          reject(new Error('Owned nested realm missing')); return;
        }
        resolve(data);
      };
      worker.postMessage({kind, nonce});
    });
  } finally { clearTimeout(timeout); worker.terminate(); }
}
