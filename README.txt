PyModder 0.7-beta: a mod loader for Geometry Dash 2.2091, mods are written in Python
===============================================================================

Install
  1. Close Geometry Dash.
  2. Extract the whole zip, then run "PyModder Setup.exe".
     It finds the game in Steam by itself (or press Browse...), then press Install.
     Updating from an older PyModder: just install over it, your mods and settings stay.
  3. Start the game as usual. The PyModder button appears in the main menu.

  No Setup.exe? install.cmd does the same in a console window.

Works with other mods
  PyModder starts through XInput1_4.dll. If that file already belongs to another
  mod loader (Geode, Mega Hack...), "Auto" puts PyModder into opengl32.dll instead,
  so both work. You can also pick the name by hand in the "Loader DLL" list.

Mods
  Folder: Geometry Dash\pymodder\mods ("PyModder Mods" shortcut on the desktop).
  Every .py file is a mod (or a folder with main.py). Template: _template.py.
  Examples: hello.py (F1), death_counter.py, slowmo.py (F2 - slow motion),
            noclip.py (F3), quick_menu.py (F4 - restart / practice / game speed), cps.py,
            rainbow.py (F9 opens its menu), trail.py, macro_bot.py (F7/F8 macros),
            confirm_exit.py ("Are you sure?" when leaving a level),
            icon_unlock.py (all icons in the garage), sprite_demo (own pictures),
            level_info_plus.py (all stats on the level page), hitboxes.py,
            icon_stealer.py (copy anyone's icons from their profile), jukebox.py (own songs
            and menu music), texture_packs.py (packs from pymodder\packs), menu_plus.py
            (main menu tweaks), cbf.py (click between frames, experimental).
  C++ example: pymodder\sdk\native_demo (copy it into mods to try it).
  Mod files (.json / .macro) are saved in Geometry Dash\pymodder\saves.
  How to write mods: Geometry Dash\pymodder\docs\API.md.

In game
  The PyModder button in the main menu or F6: the mods menu - switch mods on/off,
  settings (gear), errors (click a mod).
  F5 reloads mods without restarting the game.

If something is wrong
  Logs: pymodder\logs\python.log and pymodder\logs\loader.log.
  Switch everything off for a while: create an empty file pymodder\disabled.
  Uninstall: "PyModder Setup.exe" -> Uninstall (or uninstall.cmd).

Python is built in (3.12), you don't need to install it.

New in 0.7-beta (not tested in the game yet - send pymodder\logs\python.log if something breaks)
  - Slow motion (gd.speed, slowmo.py) uses GD's own time speed: the physics really slows down,
    not only the animations. Like GD's testmode speed, a slowed attempt does not save progress.
  - Macros (macro_bot.py, gd.Macro) are recorded by physics ticks: replays are exact at any FPS.
    Practice checkpoints and start positions work. Old macros still load.
  - Mods can put buttons on more screens: level page, your level page, level lists, level cells,
    Create screen, icon kit, editor, editor pause, level complete, profiles, options
    (gd.level_button, gd.editor_button, gd.end_button ... or gd.screen_button).
