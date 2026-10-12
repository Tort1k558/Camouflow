# Glint document delivery candidate

Unregistered, uncompiled draft outside the active Chromium checkout. No Canvas
protection or runtime capability is enabled by these files.

The Mojo schema belongs in `third_party/blink/public/mojom/native_privacy/`.
The service belongs in `content/browser/camouflow_native/`. Integration requires
the Blink Mojo GN source registration, content source/dependencies and the
document BrowserInterfaceBroker binder. None are applied during the active build.

The pinned Chromium Mojo parser/type checker and both C++ generator passes
(shared definitions and regular bindings) completed successfully outside the
active checkout. The generated callback signature matches this service and the
fixed-length Mojo byte array maps to `std::vector<uint8_t>` in browser bindings;
the service explicitly copies all 32 bytes. Private evidence:
`D:/CamouFlowNative/document-delivery-bindings-validation-complete/proof.json`.
This does not prove C++ compilation, linkage or renderer delivery.

Subsequent isolated clang-cl syntax checks passed for the service, seven-case
test translation unit and both generated C++ binding translation units, using
the existing browser target's flags and read-only headers/PCH. All temporary
outputs stayed on D outside the active output tree. Evidence:
`D:/CamouFlowNative/document-delivery-cpp-check-test-includes/proof.json`.
No objects were linked and no test cases executed.

The isolated `privacy_document_service_unittest.cc` draft uses Chromium's
RenderViewHostTestHarness, Mojo pipes, queued key loading and mock time. Seven
cases specify missing/ready/loading state, shutdown, deadline, pipe disconnect
and document destruction. They passed syntax checks but are **not registered,
linked or executed**;
they are not included in the existing 20 BrowserContext or 43 key/service cases.

The service follows pinned Chromium's `DocumentService`: cross-document navigation,
frame deletion and pipe closure destroy the receiver and invalidate readiness
callbacks. A single request per pipe and a 10-second timer bound pending work;
the existing key service additionally bounds its readiness queue. Partition and
BrowserContext come exclusively from the browser-owned RenderFrameHost. Only
the Canvas subkey crosses IPC; the root key, paths and other surface subkeys do
not. Inactive/BFCache/prerender documents cannot obtain a response seed.

Required before promotion:

- Compile the service and generated bindings, then link their real GN targets.
- Add RenderViewHostTestHarness/Mojo tests for ready/loading/error/timeout,
  duplicate requests, disconnect, navigation, frame/context shutdown, BFCache,
  opaque partitions, same/cross-site frames and independent OTR contexts.
- Verify actual renderer IPC in a linked browser with no JavaScript exposure.
- Provide policy before synchronous pixel readback: no blocking synchronous IPC,
  late unprotected first read or default identity on failure.
- Define worker transport independently from trusted browser worker hosts;
  shared/service worker partition semantics are not solved by this document pipe.
- Finalize version-1 Canvas algorithm before activating this policy. A response
  carrying version 1 here reserves a draft contract, not a released capability.

No command-line seeds, renderer-supplied StorageKeys or JavaScript getters.

## Integration draft

`integration.patch` registers the schema, browser sources, seven unit cases and
document BrowserInterfaceBroker binder. It is not applied or registered in the
build lock. After the current build finishes, copy the Mojo file to the schema
directory above and the three service C++ files to the content directory above;
then apply this integration patch. It passed applicability checks against the
001-017 source tree with input hashes unchanged. Real GN generation, dependency
checks, compilation, linkage and tests remain mandatory before promotion.
