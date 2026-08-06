"""
Linux/BlueZ specific helper functions for omblepy.

Everything in this file talks to BlueZ, either through bleak or directly
via D-Bus. Callers must confirm the operating system is Linux before
calling any function in this module.
"""

import asyncio
import logging

import bleak

logger = logging.getLogger("omblepy")

_SMP_AGENT_PATH = "/omblepy/smp_agent"


async def register_smp_agent():
    """Register a NoInputNoOutput BlueZ pairing agent via D-Bus.
    Returns the MessageBus instance (for cleanup), or None on failure."""
    try:
        from dbus_fast.aio import MessageBus
        from dbus_fast.constants import BusType
        from dbus_fast.service import ServiceInterface, method
    except ImportError:
        logger.warning("dbus-fast not installed, SMP agent not available.")
        return None

    class SmpAgent(ServiceInterface):
        """BlueZ pairing agent that accepts all pairing requests."""
        def __init__(self):
            super().__init__("org.bluez.Agent1")

        @method()
        def Release(self): pass

        @method()
        def RequestPinCode(self, device: "o") -> "s":
            logger.debug(f"SMP Agent: PinCode requested for {device}")
            return "000000"

        @method()
        def DisplayPinCode(self, device: "o", pincode: "s"):
            logger.debug(f"SMP Agent: DisplayPinCode {pincode}")

        @method()
        def RequestPasskey(self, device: "o") -> "u":
            logger.debug(f"SMP Agent: Passkey requested for {device}")
            return 0

        @method()
        def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):
            logger.debug(f"SMP Agent: DisplayPasskey {passkey:06d}")

        @method()
        def RequestConfirmation(self, device: "o", passkey: "u"):
            logger.debug(f"SMP Agent: Confirm passkey {passkey:06d}")

        @method()
        def RequestAuthorization(self, device: "o"):
            logger.debug(f"SMP Agent: Authorization requested")

        @method()
        def AuthorizeService(self, device: "o", uuid: "s"):
            logger.debug(f"SMP Agent: AuthorizeService {uuid}")

        @method()
        def Cancel(self):
            logger.debug("SMP Agent: Cancelled")

    try:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        agent = SmpAgent()
        bus.export(_SMP_AGENT_PATH, agent)

        intro = await bus.introspect("org.bluez", "/org/bluez")
        proxy = bus.get_proxy_object("org.bluez", "/org/bluez", intro)
        agent_mgr = proxy.get_interface("org.bluez.AgentManager1")

        try:
            await agent_mgr.call_unregister_agent(_SMP_AGENT_PATH)
        except Exception:
            pass

        await agent_mgr.call_register_agent(_SMP_AGENT_PATH, "NoInputNoOutput")
        await agent_mgr.call_request_default_agent(_SMP_AGENT_PATH)

        logger.info("SMP agent registered (NoInputNoOutput)")
        return bus
    except Exception as e:
        logger.warning(f"Failed to register SMP agent: {e}")
        return None


async def find_device_dbus_path(bus, address):
    """Locate the BlueZ D-Bus object path for a device address, across all adapters."""
    pathSuffix = "dev_" + address.replace(":", "_").upper()
    intro = await bus.introspect("org.bluez", "/")
    proxy = bus.get_proxy_object("org.bluez", "/", intro)
    obj_mgr = proxy.get_interface("org.freedesktop.DBus.ObjectManager")
    managedObjects = await obj_mgr.call_get_managed_objects()
    for path, interfaces in managedObjects.items():
        if path.endswith(pathSuffix) and "org.bluez.Device1" in interfaces:
            return path
    return None


async def perform_smp_pairing(bus, address):
    """Perform SMP pairing via D-Bus for the connected device with the given address."""
    try:
        dev_path = await find_device_dbus_path(bus, address)
        if dev_path is None:
            logger.warning(f"Device {address} not found on BlueZ D-Bus object tree, skipping SMP pairing step")
            return

        intro = await bus.introspect("org.bluez", dev_path)
        proxy = bus.get_proxy_object("org.bluez", dev_path, intro)
        dev_props = proxy.get_interface("org.freedesktop.DBus.Properties")
        dev_iface = proxy.get_interface("org.bluez.Device1")

        paired = await dev_props.call_get("org.bluez.Device1", "Paired")
        if paired.value:
            logger.info("Device already SMP paired")
            return

        logger.info("Performing SMP pairing...")
        await asyncio.wait_for(dev_iface.call_pair(), timeout=15.0)

        paired = await dev_props.call_get("org.bluez.Device1", "Paired")
        if paired.value:
            logger.info("SMP pairing successful")
        else:
            logger.warning("SMP pairing returned but device not paired")

        # Trust the device
        from dbus_fast import Variant
        await dev_props.call_set("org.bluez.Device1", "Trusted", Variant("b", True))

    except asyncio.TimeoutError:
        logger.warning("SMP pairing timed out (may still be OK)")
    except Exception as e:
        if "AlreadyExists" in str(e):
            logger.info("Device already paired")
        else:
            logger.warning(f"SMP pairing error: {e}")


async def unregister_smp_agent(bus):
    """Unregister the SMP agent and disconnect the D-Bus connection."""
    try:
        intro = await bus.introspect("org.bluez", "/org/bluez")
        proxy = bus.get_proxy_object("org.bluez", "/org/bluez", intro)
        agent_mgr = proxy.get_interface("org.bluez.AgentManager1")
        await agent_mgr.call_unregister_agent(_SMP_AGENT_PATH)
    except Exception:
        pass
    bus.disconnect()


async def find_device_with_active_scan(bleAddr, adapter=None, timeoutS=30):
    """Linux/BlueZ workaround: BleakClient(MAC).connect() can time out even
    when the device is advertising, because BlueZ's standard Connect path
    doesn't keep the radio actively receiving for the device. Running an
    active BleakScanner in parallel keeps BlueZ in receive mode, so it acts
    on the next advertising packet immediately. Verified empirically against
    an Omron BP5360 advertising every ~1.7s.

    Multi-adapter Linux machines also need an explicit adapter pin: BlueZ
    scopes the device record to whichever adapter discovered it, and a
    subsequent connect on a different adapter no-ops silently. We extract
    the adapter from the BLEDevice's BlueZ path after detection.

    Returns (bleDevice, adapterName, scanner). The scanner is still running
    so BlueZ stays in receive mode for the connect; the caller must stop it
    after connecting (or on failure).
    """
    logger.debug("Linux: pre-scanning to keep BlueZ in receive mode for connect.")
    found_device_holder = [None]
    found_event = asyncio.Event()
    def _detection_cb(device, _adv_data):
        if device.address.upper() == bleAddr.upper() and not found_device_holder[0]:
            found_device_holder[0] = device
            found_event.set()
    scanner_kwargs = {}
    if adapter:
        scanner_kwargs["bluez"] = {"adapter": adapter}
    scanner = bleak.BleakScanner(detection_callback=_detection_cb, scanning_mode="active", **scanner_kwargs)
    await scanner.start()
    try:
        await asyncio.wait_for(found_event.wait(), timeout=timeoutS)
    except asyncio.TimeoutError:
        await scanner.stop()
        raise OSError(f"Device {bleAddr} not advertising within {timeoutS}s. Verify it's in range and powered.")
    # Extract adapter from BlueZ device path (e.g. /org/bluez/hci1/dev_...)
    adapter_name = None
    details = getattr(found_device_holder[0], "details", None)
    if isinstance(details, dict):
        path = details.get("path") or details.get("props", {}).get("Adapter")
        if isinstance(path, str) and "/hci" in path:
            adapter_name = path.split("/")[3] if path.startswith("/org/bluez/") else None
    return found_device_holder[0], adapter_name, scanner
