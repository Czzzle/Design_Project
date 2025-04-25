import usb.core
import usb.util

# Replace with your device's Vendor ID and Product ID
dev = usb.core.find(idVendor=0x16C0, idProduct=0x048B)  # <- ADC
if dev is None:
    raise ValueError("Device not found")

dev.set_configuration()
cfg = dev.get_active_configuration()

print("Configuration:", cfg.bConfigurationValue)

for intf in cfg:
    print(f"\nInterface {intf.bInterfaceNumber}, AltSetting {intf.bAlternateSetting}")
    for ep in intf:
        dir_str = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
        print(f"  Endpoint: 0x{ep.bEndpointAddress:02X} ({dir_str})")
