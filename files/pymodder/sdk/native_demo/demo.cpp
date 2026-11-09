// PyModder native demo: counts jumps in C++, Python shows the number.
// Build:  zig c++ -target x86_64-windows-gnu -shared -O2 -s demo.cpp -o demo.dll
//    or:  cl /LD /O2 demo.cpp
#include "../pymodder.h"

static const PyModderAPI* api;
static int jumps;

// bool PlayerObject::pushButton(PlayerButton button) - 1 = jump, 2 = left, 3 = right
typedef bool (*PushButton)(void* self, int button);
static PushButton original_push;

static bool my_push(void* self, int button) {
    if (button == 1)
        jumps++;
    return original_push(self, button);      // run the game code
}

PYMODDER_EXPORT int pymodder_init(const PyModderAPI* a) {
    api = a;
    if (api->version < 1)
        return 1;
    void* target = api->address("PlayerObject::pushButton");
    if (!target) {
        api->log("PlayerObject::pushButton not found");
        return 2;
    }
    if (api->hook(target, (void*)my_push, (void**)&original_push) != 0) {
        api->log("hook failed");
        return 3;
    }
    api->log("hello from C++!");
    return 0;
}

PYMODDER_EXPORT void pymodder_unload(void) {
    api->log("bye from C++");
}

PYMODDER_EXPORT int jump_count(void) { return jumps; }
PYMODDER_EXPORT void reset_jumps(void) { jumps = 0; }
PYMODDER_EXPORT int add(int a, int b) { return a + b; }
