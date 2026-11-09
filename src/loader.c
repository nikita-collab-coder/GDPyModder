// PyModder - native part of the Python mod loader for Geometry Dash (Windows x64).
//
// The same source is built as several proxy DLLs (see gen_proxy.py / build.sh):
//   XInput1_4.dll  - libcocos2d.dll imports it (default)
//   opengl32.dll   - the game always loads it (used when XInput1_4.dll belongs to another mod,
//                    e.g. Mega Hack or Geode)
//   version.dll    - advanced, only works if something in the game loads version.dll
// Every export of the real system DLL is forwarded by an asm stub; the real DLL is loaded from
// System32 lazily on the first call. Then embedded Python from pymodder\python runs pymodder\core.
// Exports MinHook-based helpers that the Python side uses for hooks.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <wchar.h>
#include "MinHook.h"

#ifndef PROXY_FILE
#define PROXY_FILE "proxy/XInput1_4.inc"
#endif
#include PROXY_FILE

static wchar_t g_dir[MAX_PATH];   // Geometry Dash folder
static wchar_t g_self[MAX_PATH];  // full path of this DLL
static LPTOP_LEVEL_EXCEPTION_FILTER g_prevFilter;

static void logf_(const char* fmt, ...) {
    wchar_t p[MAX_PATH];
    swprintf(p, MAX_PATH, L"%ls\\pymodder\\logs\\loader.log", g_dir);
    FILE* f = _wfopen(p, L"a");
    if (!f) return;
    SYSTEMTIME t; GetLocalTime(&t);
    fprintf(f, "[%02d:%02d:%02d.%03d] ", t.wHour, t.wMinute, t.wSecond, t.wMilliseconds);
    va_list a; va_start(a, fmt); vfprintf(f, fmt, a); va_end(a);
    fputc('\n', f); fclose(f);
}

// ---------------------------------------------------------------- forwarding to the real DLL
extern void* pm_fwd[PROXY_COUNT];
static HMODULE g_real;
static INIT_ONCE g_once = INIT_ONCE_STATIC_INIT;

uintptr_t pm_missing(void) { return PROXY_MISSING_RET; }

static BOOL CALLBACK resolve_once(PINIT_ONCE o, PVOID p, PVOID* c) {
    (void)o; (void)p; (void)c;
    wchar_t path[MAX_PATH]; UINT n = GetSystemDirectoryW(path, MAX_PATH);
    swprintf(path + n, MAX_PATH - n, L"\\%ls", PROXY_DLL);
    g_real = LoadLibraryW(path);
    for (int i = 0; i < PROXY_COUNT; i++) {
        FARPROC f = g_real ? GetProcAddress(g_real, pm_names[i]) : NULL;
        pm_fwd[i] = f ? (void*)f : (void*)pm_missing;
    }
    return TRUE;
}
void pm_resolve_all(void) { InitOnceExecuteOnce(&g_once, resolve_once, NULL, NULL); }

// pm_lazy_N (generated) puts N into r10 and jumps here: save argument registers, resolve, retry.
__asm__(
    ".text\n"
    "pm_lazy_common:\n"
    "  pushq %rcx\n  pushq %rdx\n  pushq %r8\n  pushq %r9\n  pushq %r10\n"
    "  subq $0x60, %rsp\n"
    "  movdqu %xmm0, 0x20(%rsp)\n  movdqu %xmm1, 0x30(%rsp)\n"
    "  movdqu %xmm2, 0x40(%rsp)\n  movdqu %xmm3, 0x50(%rsp)\n"
    "  callq pm_resolve_all\n"
    "  movdqu 0x20(%rsp), %xmm0\n  movdqu 0x30(%rsp), %xmm1\n"
    "  movdqu 0x40(%rsp), %xmm2\n  movdqu 0x50(%rsp), %xmm3\n"
    "  addq $0x60, %rsp\n"
    "  popq %r10\n  popq %r9\n  popq %r8\n  popq %rdx\n  popq %rcx\n"
    "  leaq pm_fwd(%rip), %r11\n"
    "  jmpq *(%r11,%r10,8)\n");

// ---------------------------------------------------------------- API for Python (ctypes)
int pymodder_hook(void* target, void* detour, void** original) {
    int r = MH_CreateHook(target, detour, original);
    if (r == MH_OK) r = MH_EnableHook(target);
    return r;
}
int pymodder_unhook(void* target) {
    MH_DisableHook(target);
    return MH_RemoveHook(target);
}
const char* pymodder_status(int code) { return MH_StatusToString((MH_STATUS)code); }
const wchar_t* pymodder_dir(void) { return g_dir; }
const wchar_t* pymodder_loader(void) { return g_self; }
int pymodder_version(void) { return 3; }

// ---------------------------------------------------------------- crash log
static LONG WINAPI on_crash(EXCEPTION_POINTERS* e) {
    void* a = e->ExceptionRecord->ExceptionAddress;
    HMODULE m = NULL; wchar_t mod[MAX_PATH] = L"?";
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCWSTR)a, &m);
    if (m) GetModuleFileNameW(m, mod, MAX_PATH);
    const wchar_t* base = wcsrchr(mod, L'\\');
    logf_("CRASH 0x%08lX at %p = %ls+0x%llx", e->ExceptionRecord->ExceptionCode, a,
          base ? base + 1 : mod, (unsigned long long)((uintptr_t)a - (uintptr_t)m));
    return g_prevFilter ? g_prevFilter(e) : EXCEPTION_CONTINUE_SEARCH;
}

// ---------------------------------------------------------------- Python boot
typedef void (*Py_InitializeEx_t)(int);
typedef int (*PyRun_SimpleString_t)(const char*);
typedef void* (*PyEval_SaveThread_t)(void);

static const char* BOOT_PY =
    "import sys, os\n"
    "PM = os.path.join(r'''%s''', 'pymodder')\n"
    "os.environ['PYMODDER_LOADER'] = r'''%s'''\n"
    "os.makedirs(os.path.join(PM, 'logs'), exist_ok=True)\n"
    "_log = open(os.path.join(PM, 'logs', 'python.log'), 'w', encoding='utf-8', buffering=1, errors='replace')\n"
    "sys.stdout = sys.stderr = _log\n"
    "try:\n"
    "    sys.path.insert(0, os.path.join(PM, 'core'))\n"
    "    import pymodder_boot\n"
    "    pymodder_boot.main(PM, _log)\n"
    "except BaseException:\n"
    "    import traceback; traceback.print_exc()\n";

static DWORD WINAPI boot_thread(LPVOID unused) {
    (void)unused;
    wchar_t pydir[MAX_PATH], pat[MAX_PATH], dll[MAX_PATH] = L"";
    swprintf(pydir, MAX_PATH, L"%ls\\pymodder\\python", g_dir);
    swprintf(pat, MAX_PATH, L"%ls\\python3*.dll", pydir);
    WIN32_FIND_DATAW fd; HANDLE h = FindFirstFileW(pat, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (_wcsicmp(fd.cFileName, L"python3.dll") != 0) {
                swprintf(dll, MAX_PATH, L"%ls\\%ls", pydir, fd.cFileName);
                break;
            }
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    if (!dll[0]) { logf_("Python not found in pymodder\\python - run PyModder Setup again"); return 1; }
    HMODULE py = LoadLibraryExW(dll, NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!py) { logf_("cannot load %ls (error %lu)", dll, GetLastError()); return 1; }
    Py_InitializeEx_t init = (Py_InitializeEx_t)GetProcAddress(py, "Py_InitializeEx");
    PyRun_SimpleString_t run = (PyRun_SimpleString_t)GetProcAddress(py, "PyRun_SimpleString");
    PyEval_SaveThread_t save = (PyEval_SaveThread_t)GetProcAddress(py, "PyEval_SaveThread");
    if (!init || !run || !save) { logf_("bad Python dll"); return 1; }
    int mh = MH_Initialize();
    if (mh != MH_OK) logf_("MinHook init: %s", MH_StatusToString((MH_STATUS)mh));

    static char dir8[MAX_PATH * 3], self8[MAX_PATH * 3];
    WideCharToMultiByte(CP_UTF8, 0, g_dir, -1, dir8, sizeof dir8, NULL, NULL);
    WideCharToMultiByte(CP_UTF8, 0, g_self, -1, self8, sizeof self8, NULL, NULL);
    static char code[8192];
    snprintf(code, sizeof code, BOOT_PY, dir8, self8);
    logf_("starting Python: %ls", dll);
    init(0);
    int r = run(code);
    logf_("Python boot finished (%d), see pymodder\\logs\\python.log", r);
    save();  // release the GIL: hooks on the game thread take it when needed
    g_prevFilter = SetUnhandledExceptionFilter(on_crash);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE self, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason != DLL_PROCESS_ATTACH) return TRUE;
    DisableThreadLibraryCalls(self);
    GetModuleFileNameW(self, g_self, MAX_PATH);
    wcscpy_s(g_dir, MAX_PATH, g_self);
    wchar_t* s = wcsrchr(g_dir, L'\\'); if (s) *s = 0;

    wchar_t exe[MAX_PATH]; GetModuleFileNameW(NULL, exe, MAX_PATH);
    const wchar_t* name = wcsrchr(exe, L'\\'); name = name ? name + 1 : exe;
    if (_wcsicmp(name, L"GeometryDash.exe") != 0) return TRUE;  // only inside the game

    // only one PyModder loader per process (e.g. an old XInput1_4.dll and a new opengl32.dll)
    wchar_t mx[64]; swprintf(mx, 64, L"Local\\PyModder.loader.%lu", GetCurrentProcessId());
    HANDLE m = CreateMutexW(NULL, FALSE, mx);
    if (m && GetLastError() == ERROR_ALREADY_EXISTS) { CloseHandle(m); return TRUE; }

    wchar_t p[MAX_PATH];
    swprintf(p, MAX_PATH, L"%ls\\pymodder\\logs", g_dir); CreateDirectoryW(p, NULL);
    swprintf(p, MAX_PATH, L"%ls\\pymodder\\logs\\loader.log", g_dir); DeleteFileW(p);
    logf_("PyModder loader 3 (%ls) in %ls", PROXY_DLL, exe);

    // we took the place of Geode's XInput1_4.dll (old installers did that): start Geode ourselves
    if (_wcsicmp(PROXY_DLL, L"XInput1_4.dll") == 0) {
        swprintf(p, MAX_PATH, L"%ls\\Geode.dll", g_dir);
        if (GetFileAttributesW(p) != INVALID_FILE_ATTRIBUTES) { LoadLibraryW(p); logf_("Geode.dll loaded too"); }
    }

    swprintf(p, MAX_PATH, L"%ls\\pymodder\\disabled", g_dir);
    if (GetFileAttributesW(p) != INVALID_FILE_ATTRIBUTES) { logf_("pymodder\\disabled exists - mods are off"); return TRUE; }

    HANDLE t = CreateThread(NULL, 0, boot_thread, NULL, 0, NULL);
    if (t) CloseHandle(t);
    return TRUE;
}
