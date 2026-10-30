const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const source = fs.readFileSync(process.argv[2], 'utf8');
const start = source.indexOf('FrameSession = class _FrameSession {');
const end = source.indexOf('\n    };', start) + '\n    };'.length;
assert(start >= 0 && end > start);
const errors = [];
class Context {
  constructor(delegate, frame, world) { this.frame = frame; this.world = world; this.results = []; }
  async evaluateExpression(expression, options, arg) {
    if (this.evaluateMock) return await this.evaluateMock(expression, options, arg);
    this.results.push(arg);
  }
}
const Session = vm.runInNewContext(source.slice(start, end) + '\nFrameSession;', {
  CRExecutionContext: class {}, FrameExecutionContext: Context, TargetClosedError: Error,
  eventsHelper: { removeEventListeners() {} }, debugLogger: { log: (_, error) => errors.push(String(error)) },
});
const flush = () => new Promise(resolve => setImmediate(resolve));
function fixture(launchOptions = {ignoreDefaultArgs: ['--disable-back-forward-cache']}) {
  const frames = new Map();
  let main = null;
  function frame(id, parent) {
    return { _id: id, _parent: parent, contexts: new Map(),
      contextCreated(world, context) { this.contexts.set(world, context); },
      contextDestroyed(context) { if (this.contexts.get(context.world) === context) this.contexts.delete(context.world); },
    };
  }
  const manager = {
    frame: id => frames.get(id),
    frameAttached(id, parent) {
      if (!parent) {
        if (main) { frames.delete(main._id); main._id = id; }
        else main = frame(id, null);
        frames.set(id, main);
      } else frames.set(id, frame(id, frames.get(parent)));
    },
    frameCommittedNewDocumentNavigation(id, url, name, loader) {
      const target = frames.get(id);
      assert(target);
      for (const [key, child] of frames) if (child._parent === target) frames.delete(key);
      Object.assign(target, { url, name, loader });
    },
  };
  manager.frameAttached('away', null);
  const received = [], navigated = [];
  const page = { frameManager: manager, closeReason: () => undefined, waitForInitializedOrError: async () => page,
    onBindingCalled: async (payload, context) => received.push({ payload, frame: context.frame._id }),
    frameNavigatedToNewDocument: value => navigated.push(value._id) };
  let reply;
  const client = { send: method => { assert.equal(method, 'Page.getFrameTree'); return new Promise(resolve => { reply = resolve; }); }, dispose() {} };
  const crPage = { _page: page, _targetId: 'root', _sessions: new Map(),
    _browserContext: {_browser: {options: {originalLaunchOptions: launchOptions}}},
    _sessionForFrame: frame => {
      for (let cursor = frame; cursor; cursor = cursor._parent) {
        const owner = crPage._sessions.get(cursor._id);
        if (owner) return owner;
      }
      return session;
    }, _networkManager: { removeSession() {} } };
  const session = new Session(crPage, client, 'root', null);
  crPage._sessions.set('root', session);
  const root = { id: 'root', loaderId: 'cached', url: 'http://owned.test/', name: '' };
  const tree = { frame: root, childFrames: [{ frame: { id: 'child', loaderId: 'child-cached', url: 'http://owned.test/child', name: 'same' } }] };
  return { crPage, page, session, manager, frames, received, navigated, root, tree, reply: value => reply(value) };
}
const context = (id, frameId) => ({ id, uniqueId: 'unique-' + frameId + '-' + id, name: '', auxData: { frameId, isDefault: true } });
async function queueAndRestore(change) {
  const item = fixture();
  item.session._onExecutionContextCreated(context(1, 'root'));
  item.session._onExecutionContextCreated(context(2, 'child'));
  await item.session._onBindingCalled({ executionContextId: 1, payload: 'owned-root-event' });
  await item.session._onBindingCalled({ executionContextId: 2, payload: 'owned-child-event' });
  assert.equal(item.received.length, 0);
  assert.equal(item.session._pendingBindingEvents.length, 2);
  item.session._onFrameNavigated(item.root, false, true);
  if (change) change(item);
  item.reply({ frameTree: item.tree });
  await flush();
  await flush();
  return item;
}
const results = [];
async function test(name, run) { await run(); results.push({ name, passed: true }); }
(async () => {
  await test('restores-root-child-contexts-and-delivers-queued-bindings-once', async () => {
    const item = await queueAndRestore();
    assert.equal(item.received.length, 2);
    assert.deepEqual(item.received.map(event => event.frame).sort(), ['child', 'root']);
    assert.equal(item.session._pendingBindingEvents.length, 0);
    assert.equal(item.session._contextIdToContext.size, 2);
    assert.deepEqual(item.navigated, ['root']);
    assert.equal(item.frames.get('child')._parent, item.frames.get('root'));
  });
  await test('clear-invalidates-queued-events-and-stale-tree-reply', async () => {
    const item = await queueAndRestore(value => value.session._onExecutionContextsCleared());
    assert.equal(item.received.length, 0);
    assert.equal(item.navigated.length, 0);
    assert.equal(item.session._contextPayloads.size, 0);
  });
  await test('destroyed-context-does-not-deliver-queued-events', async () => {
    const item = await queueAndRestore(value => value.session._onExecutionContextDestroyed(1));
    assert.deepEqual(item.received.map(event => event.frame), ['child']);
    assert.equal(item.session._contextIdToContext.has(1), false);
  });
  await test('wrong-loader-tree-is-not-applied', async () => {
    const item = await queueAndRestore(value => { value.tree = { frame: { ...value.root, loaderId: 'unrelated' } }; });
    assert.equal(item.received.length, 0);
    assert.equal(item.navigated.length, 0);
    assert(item.frames.has('away'));
  });
  await test('dispose-invalidates-tree-and-clears-retained-data', async () => {
    const item = await queueAndRestore(value => value.session.dispose());
    assert.equal(item.received.length, 0);
    assert.equal(item.navigated.length, 0);
    assert.equal(item.session._contextPayloads.size, 0);
  });
  await test('unknown-unattributed-binding-is-not-queued', async () => {
    const item = fixture();
    await item.session._onBindingCalled({ executionContextId: 99, payload: 'unattributed' });
    assert.equal(item.received.length, 0);
    assert.equal(item.session._pendingBindingEvents.length, 0);
  });
  await test('existing-context-binding-path-remains-direct', async () => {
    const item = fixture();
    item.manager.frameAttached('root', null);
    item.session._onExecutionContextCreated(context(1, 'root'));
    await item.session._onBindingCalled({ executionContextId: 1, payload: 'direct' });
    assert.equal(item.received.length, 1);
    assert.equal(item.session._pendingBindingEvents.length, 0);
  });
  async function remoteRestore(change, responseChange) {
    const item = fixture();
    const remotes = [];
    for (const [id, parent] of [['remote-same', 'root'], ['remote-nested', 'child']]) {
      let reply;
      const client = { send: method => {
        assert.equal(method, 'Page.getFrameTree');
        return new Promise(resolve => { reply = resolve; });
      }, dispose() {} };
      const session = new Session(item.crPage, client, id, item.session);
      item.crPage._sessions.set(id, session);
      session._onExecutionContextCreated(context(71, id));
      await session._onBindingCalled({executionContextId: 71, payload: id});
      remotes.push({ session, id, parent, reply: value => reply(value) });
    }
    item.session._onFrameNavigated(item.root, false, true);
    item.reply({frameTree: item.tree});
    await flush();
    assert(item.frames.has('away'), 'tree must not mutate before all session snapshots are available');
    if (change) change(item, remotes);
    for (const remote of remotes) {
      const frame = {id: remote.id, parentId: remote.parent, loaderId: 'retained-' + remote.id,
        name: remote.id, url: 'http://other.owned.test/' + remote.id};
      if (responseChange) responseChange(frame, remote);
      remote.reply({frameTree: {frame}});
    }
    await flush();
    await flush();
    return {item, remotes};
  }
  await test('restores-main-and-nested-cross-process-session-contexts', async () => {
    const {item, remotes} = await remoteRestore();
    assert.deepEqual(item.navigated, ['root']);
    assert.deepEqual(item.received.map(event => event.frame).sort(), ['remote-nested', 'remote-same']);
    assert.equal(item.frames.get('remote-same')._parent, item.frames.get('root'));
    assert.equal(item.frames.get('remote-nested')._parent, item.frames.get('child'));
    assert(remotes.every(remote => remote.session._contextIdToContext.size === 1));
  });
  await test('remote-context-clear-invalidates-the-whole-pending-restore', async () => {
    const {item} = await remoteRestore((_, remotes) => remotes[0].session._onExecutionContextsCleared());
    assert(item.frames.has('away'));
    assert.equal(item.navigated.length, 0);
    assert.equal(item.received.length, 0);
  });
  await test('remote-session-replacement-invalidates-the-whole-pending-restore', async () => {
    const {item} = await remoteRestore((item, remotes) => item.crPage._sessions.delete(remotes[1].id));
    assert(item.frames.has('away'));
    assert.equal(item.navigated.length, 0);
  });
  await test('missing-remote-parent-is-rejected-before-frame-mutation', async () => {
    const {item} = await remoteRestore(null, frame => { frame.parentId = 'unrelated'; });
    assert(item.frames.has('away'));
    assert.equal(item.navigated.length, 0);
    assert.equal(errors.pop(), 'Error: Incomplete BFCache cross-process frame ancestry');
  });
  await test('cyclic-remote-ancestry-is-rejected-before-frame-mutation', async () => {
    const {item} = await remoteRestore(null, frame => {
      frame.parentId = frame.id === 'remote-same' ? 'remote-nested' : 'remote-same';
    });
    assert(item.frames.has('away'));
    assert.equal(item.navigated.length, 0);
    assert.equal(errors.pop(), 'Error: Incomplete BFCache cross-process frame ancestry');
  });
  await test('conflicting-session-frame-loaders-are-rejected-before-mutation', async () => {
    const {item} = await remoteRestore(null, frame => { frame.id = 'child'; frame.parentId = 'root'; });
    assert(item.frames.has('away'));
    assert.equal(item.navigated.length, 0);
    assert.equal(errors.pop(), 'Error: Conflicting BFCache frame snapshots');
  });
  function replyFixture() {
    const item = fixture();
    item.manager.frameAttached('root', null);
    const payload = context(1, 'root');
    item.session._onExecutionContextCreated(payload);
    return { ...item, payload, context: item.session._contextIdToContext.get(1) };
  }
  const outcome = {name: 'ownedBinding', seq: 1, result: 'owned-result'};
  await test('binding-result-delivers-once-to-current-context', async () => {
    const item = replyFixture();
    await item.context.deliverBindingResult('ownedController', outcome);
    assert.deepEqual(item.context.results, [outcome]);
    assert.equal(item.session._bindingReplies.size, 0);
  });
  await test('binding-error-payload-is-preserved', async () => {
    const item = replyFixture();
    const error = {name: 'ownedBinding', seq: 2, error: new Error('owned failure')};
    await item.context.deliverBindingResult('ownedController', error);
    assert.equal(item.context.results[0], error);
  });
  await test('binding-result-waits-for-original-unique-context-not-reused-numeric-id', async () => {
    const item = replyFixture();
    item.session._onExecutionContextsCleared();
    await item.context.deliverBindingResult('ownedController', outcome);
    assert.equal(item.session._bindingReplies.size, 1);
    item.session._onExecutionContextCreated({...item.payload, uniqueId: 'different-context'});
    await flush();
    assert.equal(item.session._contextIdToContext.get(1).results.length, 0);
    assert.equal(item.session._bindingReplies.size, 1);
    item.session._onExecutionContextsCleared();
    item.session._onExecutionContextCreated(item.payload);
    await flush();
    assert.deepEqual(item.session._contextIdToContext.get(1).results, [outcome]);
    assert.equal(item.session._bindingReplies.size, 0);
  });
  await test('binding-result-rejects-foreign-frame-with-matching-unique-id', async () => {
    const item = replyFixture();
    item.session._onExecutionContextsCleared();
    await item.context.deliverBindingResult('ownedController', outcome);
    item.manager.frameAttached('foreign', 'root');
    item.session._onExecutionContextCreated({...item.payload, auxData: {frameId: 'foreign', isDefault: true}});
    await flush();
    assert.equal(item.session._contextIdToContext.get(1).results.length, 0);
    assert.equal(item.session._bindingReplies.size, 1);
  });
  await test('explicit-unique-context-destruction-drops-retained-outcome', async () => {
    const item = replyFixture();
    item.session._onExecutionContextsCleared();
    await item.context.deliverBindingResult('ownedController', outcome);
    item.session._onExecutionContextDestroyed(1, item.payload.uniqueId);
    assert.equal(item.session._bindingReplies.size, 0);
  });
  await test('dispose-clears-retained-binding-outcomes', async () => {
    const item = replyFixture();
    item.session._onExecutionContextsCleared();
    await item.context.deliverBindingResult('ownedController', outcome);
    item.session.dispose();
    assert.equal(item.session._bindingReplies.size, 0);
  });
  await test('non-navigation-binding-delivery-errors-are-not-queued-as-success', async () => {
    const item = replyFixture();
    item.context.evaluateMock = async () => { throw new Error('Owned serialization failure'); };
    await assert.rejects(item.context.deliverBindingResult('ownedController', outcome), /Owned serialization failure/);
    assert.equal(item.session._bindingReplies.size, 0);
  });
  await test('navigation-binding-delivery-errors-wait-for-reexposed-context', async () => {
    const item = replyFixture();
    item.context.evaluateMock = async () => { throw new Error('Execution context was destroyed'); };
    await item.context.deliverBindingResult('ownedController', outcome);
    assert.equal(item.session._bindingReplies.size, 1);
    item.session._onExecutionContextsCleared();
    item.session._onExecutionContextCreated(item.payload);
    await flush();
    assert.equal(item.session._bindingReplies.size, 0);
  });
  await test('pending-binding-outcomes-are-bounded-and-overflow-is-explicit', async () => {
    const item = replyFixture();
    item.session._onExecutionContextsCleared();
    for (let seq = 0; seq < 1024; seq++)
      await item.context.deliverBindingResult('ownedController', {...outcome, seq});
    await assert.rejects(item.context.deliverBindingResult('ownedController', {...outcome, seq: 1024}), /limit exceeded/);
    assert.equal(item.session._bindingReplies.size, 1024);
  });
  await test('late-old-context-failure-does-not-starve-an-already-restored-reply', async () => {
    const item = replyFixture();
    let reject;
    item.context.evaluateMock = () => new Promise((_, fail) => { reject = fail; });
    const pending = item.context.deliverBindingResult('ownedController', outcome);
    item.session._onExecutionContextsCleared();
    item.session._onExecutionContextCreated(item.payload);
    reject(new Error('Execution context was destroyed'));
    await pending;
    await flush();
    await flush();
    assert.equal(item.session._bindingReplies.size, 0);
    assert.deepEqual(item.session._contextIdToContext.get(1).results, [outcome]);
  });
  await test('disposed-session-cannot-retain-new-binding-results', async () => {
    const item = replyFixture();
    item.session.dispose();
    await assert.rejects(item.context.deliverBindingResult('ownedController', outcome));
    assert.equal(item.session._bindingReplies.size, 0);
  });
  await test('duplicate-result-delivery-does-not-resolve-a-binding-twice', async () => {
    const item = replyFixture();
    let resolved = 0;
    const callbacks = new Map([[outcome.seq, true]]);
    const controller = {
      _bindings: new Map([[outcome.name, {callbacks}]]),
      deliverBindingResult(arg) { resolved++; callbacks.delete(arg.seq); },
    };
    item.context.evaluateMock = async (expression, _, arg) => {
      const deliver = vm.runInNewContext('(' + expression + ')', {globalThis: {ownedController: controller}});
      deliver(arg);
    };
    await item.context.deliverBindingResult('ownedController', outcome);
    await item.context.deliverBindingResult('ownedController', outcome);
    assert.equal(resolved, 1);
    assert.equal(item.session._bindingReplies.size, 0);
  });
  for (const [name, options] of [
    ['missing-option', {}], ['boolean-is-not-an-optin', {ignoreDefaultArgs: true}],
    ['string-is-not-an-optin', {ignoreDefaultArgs: '--disable-back-forward-cache'}],
    ['other-ignored-default-is-not-an-optin', {ignoreDefaultArgs: ['--enable-automation']}],
  ]) {
    await test('default-launch-path-' + name, async () => {
      const item = fixture(options);
      assert.equal(item.session._bfcacheCompatibilityEnabled, false);
      item.manager.frameAttached('root', null);
      item.session._onExecutionContextCreated(context(1, 'root'));
      const current = item.session._contextIdToContext.get(1);
      assert.equal(Object.hasOwn(current, 'deliverBindingResult'), false);
      assert.equal(item.session._contextPayloads.size, 0);
      item.session._restoreBfcacheFrameTree = () => { throw new Error('Unexpected opt-in restore'); };
      item.session._onFrameNavigated(item.root, false, true);
      await item.session._onBindingCalled({executionContextId: 1, payload: 'legacy'});
      assert.equal(item.received.length, 1);
      assert.equal(item.session._pendingBindingEvents.length, 0);
    });
  }
  await test('explicit-ignore-default-array-enables-compatibility', async () => {
    const item = fixture({ignoreDefaultArgs: ['--enable-automation', '--disable-back-forward-cache']});
    assert.equal(item.session._bfcacheCompatibilityEnabled, true);
  });
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: true, tests: results.length, results,
    scope: 'Extracted exact prototype FrameSession methods with modeled frame/client fixtures; not real browser admission' }));
})().catch(error => { console.error(error); process.exitCode = 1; });
