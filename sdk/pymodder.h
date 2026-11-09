// PyModder SDK - native (C/C++) code for PyModder mods.          API version 1
//
// Build a 64-bit .dll, put it next to your mod and load it from Python:
//     lib = gd.load_dll("mymod.dll")
// PyModder calls your exported pymodder_init(api) right after loading, and pymodder_unload()
// before the mod is unloaded (F5 / mod switched off). Hooks made with api->hook are removed for you.
//
// Visual Studio:  cl /LD /O2 mymod.cpp
// MinGW / zig:    g++ -shared -O2 -static mymod.cpp -o mymod.dll
//                 zig c++ -target x86_64-windows-gnu -shared -O2 mymod.cpp -o mymod.dll
//
// Game functions: GD 2.2 for Windows is built with MSVC, x64 calling convention:
// member functions get `this` as the first argument, e.g. bool PlayerObject::pushButton(PlayerButton)
// is  bool (*)(void* self, int button).  Names and signatures: pymodder/bindings/*.json or Geode bindings.
#ifndef PYMODDER_H
#define PYMODDER_H
#include <stdint.h>

#ifdef __cplusplus
#define PYMODDER_EXTERN_C extern "C"
#else
#define PYMODDER_EXTERN_C
#endif
#define PYMODDER_EXPORT PYMODDER_EXTERN_C __declspec(dllexport)

#define PYMODDER_API_VERSION 1

typedef struct PyModderAPI {
    int version;                 // PYMODDER_API_VERSION
    int size;                    // sizeof(PyModderAPI) on the PyModder side
    void* gd_base;               // GeometryDash.exe base address
    void* cocos_base;            // libcocos2d.dll base address
    const char* mod_dir;         // the folder of the dll (UTF-8)
    const char* mod_name;        // the mod that loaded it

    // write a line to pymodder/logs/python.log
    void (*log)(const char* text);
    // a message at the top of the screen (any thread)
    void (*notify)(const char* text, float seconds);
    // address of a game function: "PlayLayer::resetLevel" (GD, from the bindings)
    // or an export of libcocos2d.dll ("?create@CCSprite@cocos2d@@SAPEAV12@XZ"). 0 = not found.
    void* (*address)(const char* name);
    // hook a function: *original gets a pointer to call the game code. 0 = ok.
    // Works together with Python hooks (gd.hook / PyModder itself) on the same function.
    int (*hook)(void* target, void* detour, void** original);
    int (*unhook)(void* target);
    // the fastest hook (plain MinHook, no Python in between); fails if the function is already hooked
    int (*hook_raw)(void* target, void* detour, void** original);
    // run func(arg) on the game thread on the next frame (safe from your own threads)
    void (*later)(void (*func)(void*), void* arg);
    // send an event to Python:  @lib.on("name") def f(data): ...
    void (*emit)(const char* event, const char* data);
    // call a Python function made with lib.expose("name", f). Returns its result as text
    // (valid until the next call), or NULL if there is no such function / it failed.
    const char* (*call)(const char* func, const char* arg);
} PyModderAPI;

// Your dll may export these (both optional):
//   PYMODDER_EXPORT int  pymodder_init(const PyModderAPI* api);   // return 0 = ok
//   PYMODDER_EXPORT void pymodder_unload(void);

#endif
