"""Exact measured driver argument override; not runtime policy admission."""
import hashlib
from pathlib import Path

NODE_SHA256 = '3331e1ffe19874215472217c5e94f5a0c6d8e18c4ac7111d3937aa0ad5e9b4a5'
BUNDLE_SHA256 = '26c93a2ec2d48fb890d3b7d5b5fa3ee2c4a9514d1b12de26c31d6b06c4ea076c'
ORIGINAL_DISABLED_FEATURES = '--disable-features=AvoidUnnecessaryBeforeUnloadCheckSync,BoundaryEventDispatchTracksNodeRemoval,DestroyProfileOnBrowserClose,DialMediaRouteProvider,GlobalMediaControls,HttpsUpgrades,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,Translate,AutoDeElevate,RenderDocument,OptimizationHints,msForceBrowserSignIn,msEdgeUpdateLaunchServicesPreferredVersion'
PARTITIONED_DISABLED_FEATURES = '--disable-features=AvoidUnnecessaryBeforeUnloadCheckSync,BoundaryEventDispatchTracksNodeRemoval,DestroyProfileOnBrowserClose,DialMediaRouteProvider,GlobalMediaControls,HttpsUpgrades,LensOverlay,MediaRouter,PaintHolding,Translate,AutoDeElevate,RenderDocument,OptimizationHints,msForceBrowserSignIn,msEdgeUpdateLaunchServicesPreferredVersion'


def surface_driver_arguments(driver_directory: Path) -> dict:
    root = Path(driver_directory)
    if not root.is_absolute() or root != root.resolve() or not root.is_dir():
        raise ValueError("Surface policy requires a canonical measured Playwright driver")
    for relative, expected in (("node.exe", NODE_SHA256),
                               ("package/lib/coreBundle.js", BUNDLE_SHA256)):
        path = root / relative
        if path != path.resolve() or not path.is_file():
            raise ValueError("Surface policy driver file is missing or linked")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("Surface policy driver bytes are not reviewed")
    return {"ignore_default_args": [ORIGINAL_DISABLED_FEATURES],
            "arguments": [PARTITIONED_DISABLED_FEATURES]}
