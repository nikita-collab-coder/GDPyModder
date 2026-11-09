# PyModder 0.7-beta

> **A Python-based mod loader for Geometry Dash 2.2091.**  
> Write, hot-reload, and run GD mods directly in Python 3.12 without external runtime dependencies.

---

## ⚡ Features

* **Built-in Python 3.12:** No separate Python installation needed.
* **Hot-Reloading:** Reload mods on the fly with a single keystroke without restarting the game.
* **Coexistence Support:** Works seamlessly alongside Geode, Mega Hack, and other loaders via configurable hook DLLs (`XInput1_4.dll`, `opengl32.dll`).
* **Rich Native API:** Access physics hooks, custom UI injection, tick-accurate macros, and audio overrides.
* **C++ Extensibility:** Native C++ SDK available for high-performance extensions alongside Python scripts.

---

## 📦 Installation

1. **Close Geometry Dash** if it is currently running.
2. Extract the archive and launch **`PyModder Setup.exe`**.
   * The installer automatically locates your Steam directory (or click **Browse...** to select manually).
   * Click **Install**.
   * *Updating?* Run the installer over your current installation; existing mods, macros, and configuration files are preserved.
   * *No GUI?* Run `install.cmd` to perform the same setup via the command prompt.
3. Launch Geometry Dash. The **PyModder** button will appear on the main menu.

### Compatibility with Other Loaders
PyModder defaults to hooking via `XInput1_4.dll`. If that library is already in use by another mod loader (such as Geode or Mega Hack):
* Selecting **Auto** automatically switches PyModder to hook via `opengl32.dll`, allowing both loaders to run simultaneously.
* You can also manually choose the target proxy DLL from the **Loader DLL** dropdown in the installer.

---

## 🎮 In-Game Controls & Interface

| Key / Action | Function |
| :--- | :--- |
| **PyModder Button** / <kbd>F6</kbd> | Open the PyModder menu (toggle mods, configure settings via gear icon, view error logs) |
| <kbd>F5</kbd> | **Hot-reload all mods** instantly without restarting Geometry Dash |

---

## 🧩 Managing & Creating Mods

All mods reside in your game directory under:
```text
Geometry Dash/pymodder/mods/
