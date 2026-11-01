self.onmessage = async ({data}) => {
  if (!data || typeof data.nonce !== 'string' || data.nonce.length !== 36
      || !['probe', 'nested'].includes(data.kind)) return;
  const realm = {origin: self.location.origin, url: self.location.href,
    secure: isSecureContext, dedicated: self instanceof DedicatedWorkerGlobalScope};
  try {
    let value;
    let nestedRealm;
    if (data.kind === 'probe') {
      value = await probeWebGPU();
    } else {
      const child = new Worker('/bound-worker.js');
      let timeout;
      try {
        const reply = await new Promise((resolve, reject) => {
          timeout = setTimeout(() => reject(new Error('Owned nested worker timeout')), 80000);
          child.onerror = event => reject(new Error(event.message));
          child.onmessage = ({data: reply}) => {
            if (!reply || reply.nonce !== data.nonce || !reply.realm || !reply.realm.secure
                || !reply.realm.dedicated || reply.realm.origin !== self.location.origin
                || reply.realm.url !== new URL('/bound-worker.js', self.location.href).href) {
              reject(new Error('Nested worker realm/nonce mismatch')); return;
            }
            if (reply.error) reject(new Error(reply.error)); else resolve(reply);
          };
          child.postMessage({kind: 'probe', nonce: data.nonce});
        });
        value = reply.value;
        nestedRealm = reply.realm;
      } finally { clearTimeout(timeout); child.terminate(); }
    }
    self.postMessage({nonce: data.nonce, realm, nestedRealm, value});
  } catch (error) {
    self.postMessage({nonce: data.nonce, realm, error: String(error && error.stack || error)});
  }
};
