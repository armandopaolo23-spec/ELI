import winreg

def disable_realtek_power_save():
    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e96c-e325-11ce-bfc1-08002be10318}"
    base_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base)
    
    i = 0
    while True:
        try:
            subkey_name = winreg.EnumKey(base_key, i)
            subkey_path = f"{base}\\{subkey_name}"
            subkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path)
            try:
                desc, _ = winreg.QueryValueEx(subkey, "DriverDesc")
                if "realtek" in desc.lower():
                    ps_path = f"{subkey_path}\\PowerSettings"
                    ps_key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE, ps_path,
                        access=winreg.KEY_SET_VALUE
                    )
                    winreg.SetValueEx(ps_key, "ConservationIdleTime", 0, winreg.REG_BINARY, b'\xff\xff\xff\xff')
                    winreg.SetValueEx(ps_key, "PerformanceIdleTime", 0, winreg.REG_BINARY, b'\xff\xff\xff\xff')
                    winreg.SetValueEx(ps_key, "IdlePowerState", 0, winreg.REG_BINARY, b'\x00\x00\x00\x00')
                    winreg.CloseKey(ps_key)
                    print(f"✓ Listo: {desc}")
            except WindowsError:
                pass
            winreg.CloseKey(subkey)
            i += 1
        except WindowsError:
            break
    winreg.CloseKey(base_key)
    print("Reinicia la PC para aplicar los cambios.")

disable_realtek_power_save()