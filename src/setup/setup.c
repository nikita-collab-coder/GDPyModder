// PyModder Setup: a small Win32 installer for PyModder (Python mods for Geometry Dash 2.2091).
// Next to the exe there must be the folder "files" (files\loaders\*.dll, files\pymodder\...).
//
// Build: zig cc -target x86_64-windows-gnu -O2 -s -municode -Wl,--subsystem,windows setup.c setup.rc
//            -o "PyModder Setup.exe" -lcomctl32 -lole32 -lshell32 -luser32 -lgdi32 -ladvapi32
//
// Command line (used when restarting as administrator):
//   --gd "<folder>"  --loader 0..3 (auto, XInput1_4, opengl32, version)  --opts <bits>  --run install|uninstall
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <windows.h>
#include <commctrl.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <tlhelp32.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#include "stock_hashes.h"

#define PM_VERSION L"0.7.0-beta"
#define PM_TITLE L"PyModder 0.7-beta Setup"
#define PLEN 1024

#ifndef RRF_SUBKEY_WOW6464KEY
#define RRF_SUBKEY_WOW6464KEY 0x00010000
#endif
#ifndef RRF_SUBKEY_WOW6432KEY
#define RRF_SUBKEY_WOW6432KEY 0x00020000
#endif

// our own GUID copies, so no uuid library is needed
static const GUID my_CLSID_FileOpenDialog = {0xDC1C5A9C, 0xE88A, 0x4DDE, {0xA5, 0xA1, 0x60, 0xF8, 0x2A, 0x20, 0xAE, 0xF7}};
static const GUID my_IID_IFileOpenDialog = {0xD57C7288, 0xD4AD, 0x4768, {0xBE, 0x02, 0x9D, 0x96, 0x95, 0x32, 0xD9, 0x60}};
static const GUID my_CLSID_ShellLink = {0x00021401, 0, 0, {0xC0, 0, 0, 0, 0, 0, 0, 0x46}};
static const GUID my_IID_IShellLinkW = {0x000214F9, 0, 0, {0xC0, 0, 0, 0, 0, 0, 0, 0x46}};
static const GUID my_IID_IPersistFile = {0x0000010B, 0, 0, {0xC0, 0, 0, 0, 0, 0, 0, 0x46}};

enum {
    ID_PATH = 100, ID_BROWSE, ID_STATUS, ID_LOADER, ID_EXAMPLES, ID_SHORTCUT, ID_OPENMODS,
    ID_PROGRESS, ID_LOG, ID_INSTALL, ID_UNINSTALL, ID_CLOSE, ID_ICON, ID_TITLE, ID_SUB, ID_LBL_PATH, ID_LBL_LOADER,
    ID_HINT
};
enum { WM_APP_LOG = WM_APP + 1, WM_APP_PROGRESS, WM_APP_DONE };
enum { OP_INSTALL = 1, OP_UNINSTALL = 2 };
enum { OPT_EXAMPLES = 1, OPT_SHORTCUT = 2, OPT_OPENMODS = 4, OPT_PURGE = 8 };

static const wchar_t* LOADERS[3] = {L"XInput1_4.dll", L"opengl32.dll", L"version.dll"};
static const wchar_t* PM_DIRS[] = {L"core", L"bindings", L"python", L"docs", L"res", L"sdk"};
#define N_DIRS (sizeof PM_DIRS / sizeof *PM_DIRS)

static HINSTANCE g_inst;
static HWND g_wnd, g_path, g_browse, g_status, g_loader, g_examples, g_shortcut, g_openmods, g_progress, g_log,
    g_install, g_uninstall, g_close;
static HFONT g_font, g_title_font;
static int g_dpi = 96;
static wchar_t g_exe[PLEN], g_src[PLEN];   // this exe, <exe dir>\files
static int g_have_files;
static volatile LONG g_busy;
static COLORREF g_status_color;
static int g_installed;
static int g_preset_opts = -1;   // options from the command line for the first job

typedef struct {
    int op, loader, opts;
    wchar_t gd[PLEN];
} Job;

// ------------------------------------------------------------------ small helpers
static int S(int v) { return MulDiv(v, g_dpi, 96); }

static void join(wchar_t* out, const wchar_t* a, const wchar_t* b) {
    size_t n = wcslen(a);
    swprintf(out, PLEN, (n && a[n - 1] == L'\\') ? L"%ls%ls" : L"%ls\\%ls", a, b);
}

static int is_file(const wchar_t* p) {
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

static int is_dir(const wchar_t* p) {
    DWORD a = GetFileAttributesW(p);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

static void clean_path(wchar_t* p) {   // trim spaces / quotes / trailing backslashes
    wchar_t* s = p;
    while (*s == L' ' || *s == L'"' || *s == L'\t') s++;
    if (s != p) memmove(p, s, (wcslen(s) + 1) * sizeof(wchar_t));
    size_t n = wcslen(p);
    while (n && (p[n - 1] == L' ' || p[n - 1] == L'"' || p[n - 1] == L'\t' || p[n - 1] == L'/' ||
                 (p[n - 1] == L'\\' && !(n == 3 && p[1] == L':'))))
        p[--n] = 0;
    for (wchar_t* c = p; *c; c++)
        if (*c == L'/') *c = L'\\';
}

static void err_text(DWORD e, wchar_t* out, int cap) {
    out[0] = 0;
    if (!FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, NULL, e,
                        MAKELANGID(LANG_ENGLISH, SUBLANG_DEFAULT), out, cap, NULL) &&
        !FormatMessageW(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, NULL, e, 0, out, cap, NULL))
        swprintf(out, cap, L"error %lu", e);
    size_t n = wcslen(out);
    while (n && (out[n - 1] == L'\r' || out[n - 1] == L'\n' || out[n - 1] == L' ' || out[n - 1] == L'.'))
        out[--n] = 0;
}

static void say(const wchar_t* fmt, ...) {
    wchar_t buf[2048];
    va_list ap;
    va_start(ap, fmt);
    vswprintf(buf, 2048, fmt, ap);
    va_end(ap);
    wchar_t* copy = _wcsdup(buf);
    if (copy && !PostMessageW(g_wnd, WM_APP_LOG, 0, (LPARAM)copy)) free(copy);
}

static void log_err(const wchar_t* what, const wchar_t* path, DWORD e) {
    wchar_t m[512];
    err_text(e, m, 512);
    say(L"ERROR: %ls %ls: %ls.", what, path, m);
}

static int g_total, g_done;
static void progress_step(int n) {
    g_done += n;
    PostMessageW(g_wnd, WM_APP_PROGRESS, (WPARAM)g_done, (LPARAM)(g_total ? g_total : 1));
}

static int read_file(const wchar_t* path, char** data, DWORD* len) {
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
                           OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return 0;
    LARGE_INTEGER sz;
    if (!GetFileSizeEx(h, &sz) || sz.QuadPart > 256 * 1024 * 1024) {
        CloseHandle(h);
        return 0;
    }
    DWORD n = (DWORD)sz.QuadPart, rd = 0;
    char* buf = (char*)malloc(n + 1);
    if (!buf) {
        CloseHandle(h);
        return 0;
    }
    BOOL ok = n ? ReadFile(h, buf, n, &rd, NULL) : TRUE;
    CloseHandle(h);
    if (!ok || rd != n) {
        free(buf);
        return 0;
    }
    buf[n] = 0;
    *data = buf;
    *len = n;
    return 1;
}

static int write_file(const wchar_t* path, const char* data, DWORD len) {
    HANDLE h = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return 0;
    DWORD wr = 0;
    BOOL ok = WriteFile(h, data, len, &wr, NULL);
    CloseHandle(h);
    return ok && wr == len;
}

static int mem_has(const char* buf, DWORD len, const char* needle) {
    size_t k = strlen(needle);
    if (len < k) return 0;
    for (DWORD i = 0; i + k <= len; i++)
        if (buf[i] == needle[0] && !memcmp(buf + i, needle, k)) return 1;
    return 0;
}

// 0 = no file, 1 = a PyModder (or old gdpy) loader, 2 = somebody else's dll
static int loader_state(const wchar_t* path) {
    if (!is_file(path)) return 0;
    char* d;
    DWORD n;
    if (!read_file(path, &d, &n)) return 2;
    int ours = mem_has(d, n, "pymodder_hook") || mem_has(d, n, "gdpy_hook");
    free(d);
    return ours ? 1 : 2;
}

static int file_hash(const wchar_t* path, unsigned long long* out) {
    char* d;
    DWORD n;
    if (!read_file(path, &d, &n)) return 0;
    unsigned long long h = 0xcbf29ce484222325ULL;
    for (DWORD i = 0; i < n; i++) h = (h ^ (unsigned char)d[i]) * 0x100000001b3ULL;
    free(d);
    *out = h;
    return 1;
}

static int is_stock(unsigned long long h) {
    for (size_t i = 0; i < sizeof STOCK_HASHES / sizeof *STOCK_HASHES; i++)
        if (STOCK_HASHES[i] == h) return 1;
    return 0;
}

static void installed_version(const wchar_t* gd, wchar_t* out, int cap) {
    wchar_t p[PLEN], t[PLEN];
    out[0] = 0;
    join(t, gd, L"pymodder");
    join(p, t, L"install.json");
    char* d;
    DWORD n;
    if (!read_file(p, &d, &n)) return;
    char* k = strstr(d, "\"version\"");
    if (k && (k = strchr(k + 9, '"'))) {
        char* e = strchr(k + 1, '"');
        if (e && e - k < 32) {
            *e = 0;
            MultiByteToWideChar(CP_UTF8, 0, k + 1, -1, out, cap);
        }
    }
    free(d);
}

static int process_running(const wchar_t* exe) {
    HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (s == INVALID_HANDLE_VALUE) return 0;
    PROCESSENTRY32W e;
    e.dwSize = sizeof e;
    int found = 0;
    if (Process32FirstW(s, &e)) do {
            if (!_wcsicmp(e.szExeFile, exe)) {
                found = 1;
                break;
            }
        } while (Process32NextW(s, &e));
    CloseHandle(s);
    return found;
}

static int is_elevated(void) {
    HANDLE tok;
    TOKEN_ELEVATION el = {0};
    DWORD sz = 0;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &tok)) return 0;
    GetTokenInformation(tok, TokenElevation, &el, sizeof el, &sz);
    CloseHandle(tok);
    return el.TokenIsElevated != 0;
}

static DWORD try_write(const wchar_t* dir) {   // 0 = we can create files there
    wchar_t p[PLEN];
    join(p, dir, L"pymodder_setup_test.tmp");
    HANDLE h = CreateFileW(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, NULL);
    if (h == INVALID_HANDLE_VALUE) return GetLastError();
    CloseHandle(h);
    return 0;
}

// ------------------------------------------------------------------ finding the game
static int try_gd(const wchar_t* dir, wchar_t* out) {
    wchar_t p[PLEN];
    if (!dir[0]) return 0;
    join(p, dir, L"GeometryDash.exe");
    if (!is_file(p)) return 0;
    if (!GetFullPathNameW(dir, PLEN, out, NULL)) wcscpy(out, dir);
    clean_path(out);
    return 1;
}

static int try_steam(const wchar_t* steam, wchar_t* out) {
    wchar_t s[PLEN], p[PLEN];
    wcsncpy(s, steam, PLEN - 1);
    s[PLEN - 1] = 0;
    clean_path(s);
    if (!s[0]) return 0;
    join(p, s, L"steamapps\\common\\Geometry Dash");
    if (try_gd(p, out)) return 1;
    // other Steam libraries
    join(p, s, L"steamapps\\libraryfolders.vdf");
    char* d;
    DWORD n;
    if (!read_file(p, &d, &n)) return 0;
    int found = 0;
    for (char* k = d; !found && (k = strstr(k, "\"path\"")); k += 6) {
        char* q = strchr(k + 6, '"');
        if (!q) break;
        char lib[PLEN];
        int j = 0;
        for (char* c = q + 1; *c && *c != '"' && j < PLEN - 1; c++) {
            if (*c == '\\' && c[1] == '\\') c++;
            lib[j++] = *c;
        }
        lib[j] = 0;
        wchar_t wl[PLEN];
        if (!MultiByteToWideChar(CP_UTF8, 0, lib, -1, wl, PLEN)) continue;
        clean_path(wl);
        join(p, wl, L"steamapps\\common\\Geometry Dash");
        found = try_gd(p, out);
    }
    free(d);
    return found;
}

static int reg_str(HKEY root, const wchar_t* key, const wchar_t* name, DWORD flags, wchar_t* out) {
    DWORD sz = PLEN * sizeof(wchar_t);
    out[0] = 0;
    return RegGetValueW(root, key, name, RRF_RT_REG_SZ | flags, NULL, out, &sz) == ERROR_SUCCESS && out[0];
}

static int find_gd(wchar_t* out) {
    wchar_t v[PLEN], d[PLEN];
    // the installer was put into the game folder (or one level below)
    wcscpy(d, g_exe);
    for (int up = 0; up < 3; up++) {
        wchar_t* s = wcsrchr(d, L'\\');
        if (!s) break;
        *s = 0;
        if (try_gd(d, out)) return 1;
    }
    static const wchar_t* UNINST = L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Steam App 322170";
    if (reg_str(HKEY_LOCAL_MACHINE, UNINST, L"InstallLocation", RRF_SUBKEY_WOW6464KEY, v) && try_gd(v, out)) return 1;
    if (reg_str(HKEY_LOCAL_MACHINE, UNINST, L"InstallLocation", RRF_SUBKEY_WOW6432KEY, v) && try_gd(v, out)) return 1;
    if (reg_str(HKEY_CURRENT_USER, L"Software\\Valve\\Steam", L"SteamPath", 0, v) && try_steam(v, out)) return 1;
    if (reg_str(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Valve\\Steam", L"InstallPath", RRF_SUBKEY_WOW6432KEY, v) &&
        try_steam(v, out))
        return 1;
    static const wchar_t* GUESS[] = {L"C:\\Program Files (x86)\\Steam", L"C:\\Program Files\\Steam", L"C:\\Steam",
                                     L"D:\\Steam", L"D:\\SteamLibrary", L"E:\\SteamLibrary", L"D:\\Games\\Steam"};
    for (size_t i = 0; i < sizeof GUESS / sizeof *GUESS; i++)
        if (try_steam(GUESS[i], out)) return 1;
    return 0;
}

// ------------------------------------------------------------------ file operations
static int count_files(const wchar_t* dir) {
    wchar_t pat[PLEN], p[PLEN];
    WIN32_FIND_DATAW f;
    join(pat, dir, L"*");
    HANDLE h = FindFirstFileW(pat, &f);
    if (h == INVALID_HANDLE_VALUE) return 0;
    int n = 0;
    do {
        if (!wcscmp(f.cFileName, L".") || !wcscmp(f.cFileName, L"..") || !wcscmp(f.cFileName, L"__pycache__"))
            continue;
        join(p, dir, f.cFileName);
        n += (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ? count_files(p) : 1;
    } while (FindNextFileW(h, &f));
    FindClose(h);
    return n;
}

static int delete_tree(const wchar_t* dir) {
    if (!is_dir(dir)) return 1;
    wchar_t pat[PLEN], p[PLEN];
    WIN32_FIND_DATAW f;
    int ok = 1;
    join(pat, dir, L"*");
    HANDLE h = FindFirstFileW(pat, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!wcscmp(f.cFileName, L".") || !wcscmp(f.cFileName, L"..")) continue;
            join(p, dir, f.cFileName);
            if ((f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && !(f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
                ok &= delete_tree(p);
            } else if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                if (!RemoveDirectoryW(p)) ok = 0;    // a junction: remove the link only
            } else {
                SetFileAttributesW(p, FILE_ATTRIBUTE_NORMAL);
                if (!DeleteFileW(p)) {
                    log_err(L"cannot delete", p, GetLastError());
                    ok = 0;
                }
            }
        } while (FindNextFileW(h, &f));
        FindClose(h);
    }
    SetFileAttributesW(dir, FILE_ATTRIBUTE_NORMAL);
    if (!RemoveDirectoryW(dir)) ok = 0;
    return ok;
}

static int copy_one(const wchar_t* s, const wchar_t* d) {
    if (is_file(d)) SetFileAttributesW(d, FILE_ATTRIBUTE_NORMAL);
    if (!CopyFileW(s, d, FALSE)) {
        log_err(L"cannot copy to", d, GetLastError());
        return 0;
    }
    return 1;
}

static int copy_tree(const wchar_t* src, const wchar_t* dst) {
    wchar_t pat[PLEN], s[PLEN], d[PLEN];
    WIN32_FIND_DATAW f;
    if (!CreateDirectoryW(dst, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        log_err(L"cannot create", dst, GetLastError());
        return 0;
    }
    join(pat, src, L"*");
    HANDLE h = FindFirstFileW(pat, &f);
    if (h == INVALID_HANDLE_VALUE) return 1;
    int ok = 1;
    do {
        if (!wcscmp(f.cFileName, L".") || !wcscmp(f.cFileName, L"..") || !wcscmp(f.cFileName, L"__pycache__"))
            continue;
        join(s, src, f.cFileName);
        join(d, dst, f.cFileName);
        if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            ok &= copy_tree(s, d);
        } else {
            ok &= copy_one(s, d);
            progress_step(1);
        }
    } while (ok && FindNextFileW(h, &f));
    FindClose(h);
    return ok;
}

// example mods: new files are added (if wanted), files from older versions that the user didn't change are
// updated, everything else is left alone
static int sync_mods(const wchar_t* src, const wchar_t* dst, int top, int want_new, int* added, int* updated) {
    wchar_t pat[PLEN], s[PLEN], d[PLEN];
    WIN32_FIND_DATAW f;
    join(pat, src, L"*");
    HANDLE h = FindFirstFileW(pat, &f);
    if (h == INVALID_HANDLE_VALUE) return 1;
    int ok = 1;
    do {
        const wchar_t* name = f.cFileName;
        if (!wcscmp(name, L".") || !wcscmp(name, L"..") || !wcscmp(name, L"__pycache__") ||
            (top && !_wcsicmp(name, L"data")))
            continue;
        join(s, src, name);
        join(d, dst, name);
        if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            int exists = is_dir(d);
            if (exists || want_new) {
                if (!exists && !CreateDirectoryW(d, NULL)) {
                    log_err(L"cannot create", d, GetLastError());
                    ok = 0;
                    continue;
                }
                ok &= sync_mods(s, d, 0, want_new || exists, added, updated);
            } else {
                progress_step(count_files(s));
            }
            continue;
        }
        progress_step(1);
        if (is_file(d)) {
            unsigned long long hs, hd;
            if (file_hash(d, &hd) && file_hash(s, &hs) && hd != hs && is_stock(hd)) {
                if (copy_one(s, d)) (*updated)++;
                else ok = 0;
            }
            continue;
        }
        int want = want_new || name[0] == L'_';
        if (!want && top) {   // the icon of a mod the user already has
            const wchar_t* dot = wcsrchr(name, L'.');
            if (dot && !_wcsicmp(dot, L".png")) {
                wchar_t py[PLEN];
                wcscpy(py, d);
                wcscpy(py + (wcslen(d) - wcslen(dot)), L".py");
                want = is_file(py);
            }
        }
        if (want) {
            if (copy_one(s, d)) (*added)++;
            else ok = 0;
        }
    } while (FindNextFileW(h, &f));
    FindClose(h);
    return ok;
}

static int make_shortcut(const wchar_t* lnk, const wchar_t* target, const wchar_t* icon, const wchar_t* desc) {
    IShellLinkW* sl = NULL;
    IPersistFile* pf = NULL;
    HRESULT hr = CoCreateInstance(&my_CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, &my_IID_IShellLinkW, (void**)&sl);
    if (FAILED(hr)) return 0;
    IShellLinkW_SetPath(sl, target);
    if (icon) IShellLinkW_SetIconLocation(sl, icon, 0);
    IShellLinkW_SetDescription(sl, desc);
    hr = IShellLinkW_QueryInterface(sl, &my_IID_IPersistFile, (void**)&pf);
    if (SUCCEEDED(hr)) {
        hr = IPersistFile_Save(pf, lnk, TRUE);
        IPersistFile_Release(pf);
    }
    IShellLinkW_Release(sl);
    return SUCCEEDED(hr);
}

static void shortcut_path(wchar_t* out) {
    wchar_t desk[MAX_PATH];
    out[0] = 0;
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_DESKTOPDIRECTORY, NULL, 0, desk)))
        join(out, desk, L"PyModder Mods.lnk");
}

static int restore_bak(const wchar_t* dll) {
    wchar_t bak[PLEN];
    swprintf(bak, PLEN, L"%ls.bak", dll);
    if (!is_file(bak) || is_file(dll)) return 0;
    if (!MoveFileW(bak, dll)) {
        log_err(L"cannot restore", bak, GetLastError());
        return 0;
    }
    const wchar_t* name = wcsrchr(dll, L'\\');
    say(L"Restored the previous %ls (from .bak).", name ? name + 1 : dll);
    return 1;
}

// ------------------------------------------------------------------ install / uninstall
static int install_loader(const Job* j, int* picked) {
    wchar_t p[3][PLEN], bak[PLEN], src[PLEN], t[PLEN];
    int st[3];
    for (int i = 0; i < 3; i++) {
        join(p[i], j->gd, LOADERS[i]);
        st[i] = loader_state(p[i]);
    }
    int pick;
    if (j->loader == 0) {   // auto
        swprintf(bak, PLEN, L"%ls.bak", p[0]);
        if (st[0] == 1 && loader_state(bak) == 2) {
            // we took XInput1_4.dll from another mod loader earlier: give it back and move to opengl32.dll
            SetFileAttributesW(p[0], FILE_ATTRIBUTE_NORMAL);
            if (DeleteFileW(p[0]) && MoveFileW(bak, p[0])) {
                say(L"XInput1_4.dll belongs to another mod loader (Geode / Mega Hack...): restored it from .bak.");
                st[0] = 2;
            }
        }
        if (st[0] != 2) pick = 0;
        else if (st[1] != 2) pick = 1;
        else {
            say(L"ERROR: XInput1_4.dll and opengl32.dll are both used by other mods. "
                 L"Choose \"version.dll\" in the Loader list and press Install again.");
            return 0;
        }
        if (pick == 1 && st[0] == 2)
            say(L"XInput1_4.dll is used by another mod (Geode / Mega Hack...), so PyModder uses opengl32.dll.");
    } else {
        pick = j->loader - 1;
        if (st[pick] == 2) {
            swprintf(bak, PLEN, L"%ls.bak", p[pick]);
            SetFileAttributesW(bak, FILE_ATTRIBUTE_NORMAL);
            if (!MoveFileExW(p[pick], bak, MOVEFILE_REPLACE_EXISTING)) {
                log_err(L"cannot back up", p[pick], GetLastError());
                return 0;
            }
            say(L"Saved the other %ls as %ls.bak (uninstall puts it back).", LOADERS[pick], LOADERS[pick]);
        }
    }
    join(t, g_src, L"loaders");
    join(src, t, LOADERS[pick]);
    if (!copy_one(src, p[pick])) return 0;
    say(L"Loader: %ls", LOADERS[pick]);
    for (int i = 0; i < 3; i++) {
        if (i == pick || loader_state(p[i]) != 1) continue;
        SetFileAttributesW(p[i], FILE_ATTRIBUTE_NORMAL);
        if (DeleteFileW(p[i])) {
            say(L"Removed the old PyModder %ls.", LOADERS[i]);
            restore_bak(p[i]);
        } else {
            log_err(L"cannot delete", p[i], GetLastError());
        }
    }
    *picked = pick;
    return 1;
}

static int do_install(const Job* j) {
    wchar_t spm[PLEN], pm[PLEN], mods[PLEN], s[PLEN], d[PLEN];
    join(spm, g_src, L"pymodder");
    join(pm, j->gd, L"pymodder");
    join(mods, pm, L"mods");

    g_done = 0;
    g_total = 8;
    for (size_t i = 0; i < N_DIRS; i++) {
        join(s, spm, PM_DIRS[i]);
        g_total += count_files(s);
    }
    join(s, spm, L"mods");
    g_total += count_files(s);
    progress_step(0);

    say(L"Installing PyModder %ls into %ls", PM_VERSION, j->gd);
    int pick = 0;
    if (!install_loader(j, &pick)) return 0;
    progress_step(1);

    CreateDirectoryW(pm, NULL);
    CreateDirectoryW(mods, NULL);
    join(d, pm, L"logs");
    CreateDirectoryW(d, NULL);
    if (!is_dir(mods)) {
        log_err(L"cannot create", mods, GetLastError());
        return 0;
    }

    say(L"Copying PyModder files...");
    for (size_t i = 0; i < N_DIRS; i++) {
        join(s, spm, PM_DIRS[i]);
        join(d, pm, PM_DIRS[i]);
        if (!is_dir(s)) continue;
        if (is_dir(d) && !delete_tree(d)) {
            say(L"ERROR: cannot replace %ls (is Geometry Dash still running?)", d);
            return 0;
        }
        if (!copy_tree(s, d)) return 0;
    }
    progress_step(1);

    int added = 0, updated = 0;
    join(s, spm, L"mods");
    sync_mods(s, mods, 1, (j->opts & OPT_EXAMPLES) != 0, &added, &updated);
    if (added || updated) say(L"Example mods: %d added, %d updated (your own changes are kept).", added, updated);
    progress_step(1);

    join(d, pm, L"config.json");
    if (!is_file(d)) {
        join(s, spm, L"config.json");
        copy_one(s, d);
    }
    join(d, pm, L"disabled");
    if (is_file(d) && DeleteFileW(d)) say(L"Removed pymodder\\disabled (PyModder was switched off).");
    progress_step(1);

    char json[256];
    SYSTEMTIME t;
    GetLocalTime(&t);
    int n = snprintf(json, sizeof json,
                     "{\n  \"version\": \"%ls\",\n  \"loader\": \"%ls\",\n  \"installed\": \"%04d-%02d-%02d %02d:%02d\"\n}\n",
                     PM_VERSION, LOADERS[pick], t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute);
    join(d, pm, L"install.json");
    write_file(d, json, (DWORD)n);
    progress_step(1);

    if (j->opts & OPT_SHORTCUT) {
        wchar_t lnk[PLEN], ico[PLEN], r[PLEN];
        shortcut_path(lnk);
        join(r, pm, L"res");
        join(ico, r, L"pymodder.ico");
        if (lnk[0] && make_shortcut(lnk, mods, is_file(ico) ? ico : NULL, L"PyModder mods folder"))
            say(L"Desktop shortcut \"PyModder Mods\" created.");
        else
            say(L"Could not create the desktop shortcut (not a problem).");
    }
    g_done = g_total;
    progress_step(0);
    say(L"");
    say(L"Done! Start Geometry Dash as usual (through Steam).");
    say(L"In the main menu: the PyModder button or F6 opens the mods menu, F5 reloads mods.");
    say(L"Mods: %ls", mods);
    if (j->opts & OPT_OPENMODS) ShellExecuteW(NULL, L"open", mods, NULL, NULL, SW_SHOWNORMAL);
    return 1;
}

static int do_uninstall(const Job* j) {
    wchar_t p[PLEN], pm[PLEN];
    int ok = 1;
    g_done = 0;
    g_total = 5;
    progress_step(0);
    say(L"Uninstalling PyModder from %ls", j->gd);
    for (int i = 0; i < 3; i++) {
        join(p, j->gd, LOADERS[i]);
        if (loader_state(p) == 1) {
            SetFileAttributesW(p, FILE_ATTRIBUTE_NORMAL);
            if (DeleteFileW(p)) say(L"Removed %ls.", LOADERS[i]);
            else {
                log_err(L"cannot delete", p, GetLastError());
                ok = 0;
            }
        }
        restore_bak(p);
        progress_step(1);
    }
    shortcut_path(p);
    if (p[0] && is_file(p) && DeleteFileW(p)) say(L"Removed the desktop shortcut.");
    progress_step(1);
    join(pm, j->gd, L"pymodder");
    if (j->opts & OPT_PURGE) {
        if (delete_tree(pm)) say(L"Deleted the pymodder folder.");
        else {
            say(L"ERROR: could not delete everything in %ls", pm);
            ok = 0;
        }
    } else if (is_dir(pm)) {
        join(p, pm, L"install.json");
        DeleteFileW(p);
        say(L"Kept the pymodder folder (mods, saves, logs): %ls", pm);
    }
    g_done = g_total;
    progress_step(0);
    say(ok ? L"PyModder is uninstalled. Geometry Dash will start without it."
            : L"Finished with errors (see above).");
    return ok;
}

static DWORD WINAPI worker(LPVOID arg) {
    Job* j = (Job*)arg;
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    int ok = j->op == OP_INSTALL ? do_install(j) : do_uninstall(j);
    if (!ok && j->op == OP_INSTALL) say(L"Installation failed. Nothing important was lost; fix the problem and press Install again.");
    CoUninitialize();
    PostMessageW(g_wnd, WM_APP_DONE, (WPARAM)ok, (LPARAM)j->op);
    free(j);
    return 0;
}

// ------------------------------------------------------------------ UI
static void ui_log(const wchar_t* text) {
    int n = GetWindowTextLengthW(g_log);
    if (n > 60000) {
        SetWindowTextW(g_log, L"");
        n = 0;
    }
    SendMessageW(g_log, EM_SETSEL, n, n);
    if (n) SendMessageW(g_log, EM_REPLACESEL, FALSE, (LPARAM)L"\r\n");
    SendMessageW(g_log, EM_REPLACESEL, FALSE, (LPARAM)text);
    SendMessageW(g_log, EM_SCROLLCARET, 0, 0);
}

static void get_gd(wchar_t* out) {
    GetWindowTextW(g_path, out, PLEN);
    clean_path(out);
}

static void set_enabled(void) {
    int busy = g_busy != 0;
    wchar_t gd[PLEN], p[PLEN];
    get_gd(gd);
    join(p, gd, L"GeometryDash.exe");
    int game = gd[0] && is_file(p);
    EnableWindow(g_install, !busy && game && g_have_files);
    EnableWindow(g_uninstall, !busy && game && g_installed);
    EnableWindow(g_close, !busy);
    EnableWindow(g_browse, !busy);
    EnableWindow(g_path, !busy);
    EnableWindow(g_loader, !busy);
    EnableWindow(g_examples, !busy);
    EnableWindow(g_shortcut, !busy);
    EnableWindow(g_openmods, !busy);
}

static void update_status(void) {
    wchar_t gd[PLEN], p[PLEN], msg[1024], ver[64];
    get_gd(gd);
    g_installed = 0;
    if (!gd[0]) {
        wcscpy(msg, L"Choose the Geometry Dash folder (the one with GeometryDash.exe).");
        g_status_color = RGB(160, 90, 0);
    } else {
        join(p, gd, L"GeometryDash.exe");
        if (!is_file(p)) {
            wcscpy(msg, L"GeometryDash.exe is not in this folder.");
            g_status_color = RGB(200, 30, 30);
        } else {
            int st[3], ours = -1;
            for (int i = 0; i < 3; i++) {
                join(p, gd, LOADERS[i]);
                st[i] = loader_state(p);
                if (st[i] == 1 && ours < 0) ours = i;
            }
            join(p, gd, L"pymodder");
            int files = is_dir(p);
            installed_version(gd, ver, 64);
            if (ours >= 0) {
                swprintf(msg, 1024, L"PyModder %ls is installed (%ls).", ver[0] ? ver : L"(old version)", LOADERS[ours]);
                g_status_color = RGB(0, 130, 40);
            } else if (files) {
                wcscpy(msg, L"Geometry Dash found. PyModder files are there, but the loader is not installed.");
                g_status_color = RGB(160, 90, 0);
            } else {
                wcscpy(msg, L"Geometry Dash found. PyModder is not installed yet.");
                g_status_color = RGB(0, 90, 170);
            }
            g_installed = ours >= 0 || files;
            int sel = (int)SendMessageW(g_loader, CB_GETCURSEL, 0, 0);
            if (sel <= 0) {
                wchar_t bak[PLEN];
                join(p, gd, L"XInput1_4.dll.bak");
                wcscpy(bak, p);
                if (st[0] == 2)
                    wcscat(msg, st[1] == 2 ? L" XInput1_4.dll and opengl32.dll are used by other mods: choose version.dll."
                                           : L" XInput1_4.dll belongs to another mod (Geode / Mega Hack?), so PyModder will use opengl32.dll.");
                else if (st[0] == 1 && loader_state(bak) == 2)
                    wcscat(msg, L" The other mod's XInput1_4.dll will be put back, PyModder moves to opengl32.dll.");
            } else if (st[sel - 1] == 2) {
                swprintf(msg + wcslen(msg), 300, L" %ls belongs to another mod: it will be saved as %ls.bak.",
                         LOADERS[sel - 1], LOADERS[sel - 1]);
            }
            SetWindowTextW(g_install, ours >= 0 ? (wcscmp(ver, PM_VERSION) ? L"Update" : L"Reinstall") : L"Install");
        }
    }
    SetWindowTextW(g_status, msg);
    InvalidateRect(g_status, NULL, TRUE);
    set_enabled();
}

static void browse(void) {
    IFileOpenDialog* dlg = NULL;
    if (FAILED(CoCreateInstance(&my_CLSID_FileOpenDialog, NULL, CLSCTX_INPROC_SERVER, &my_IID_IFileOpenDialog,
                                (void**)&dlg)))
        return;
    DWORD o = 0;
    IFileOpenDialog_GetOptions(dlg, &o);
    IFileOpenDialog_SetOptions(dlg, o | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST);
    IFileOpenDialog_SetTitle(dlg, L"Choose the Geometry Dash folder");
    wchar_t cur[PLEN];
    get_gd(cur);
    if (cur[0] && is_dir(cur)) {
        IShellItem* it = NULL;
        typedef HRESULT(WINAPI * PCreate)(PCWSTR, IBindCtx*, REFIID, void**);
        static const GUID iid_item = {0x43826D1E, 0xE718, 0x42EE, {0xBC, 0x55, 0xA1, 0xE2, 0x61, 0xC3, 0x7B, 0xFE}};
        PCreate create = (PCreate)(void*)GetProcAddress(GetModuleHandleW(L"shell32.dll"), "SHCreateItemFromParsingName");
        if (create && SUCCEEDED(create(cur, NULL, &iid_item, (void**)&it))) {
            IFileOpenDialog_SetFolder(dlg, it);
            IShellItem_Release(it);
        }
    }
    if (SUCCEEDED(IFileOpenDialog_Show(dlg, g_wnd))) {
        IShellItem* it = NULL;
        if (SUCCEEDED(IFileOpenDialog_GetResult(dlg, &it))) {
            PWSTR path = NULL;
            if (SUCCEEDED(IShellItem_GetDisplayName(it, SIGDN_FILESYSPATH, &path))) {
                SetWindowTextW(g_path, path);
                CoTaskMemFree(path);
            }
            IShellItem_Release(it);
        }
    }
    IFileOpenDialog_Release(dlg);
    update_status();
}

static int opts_from_ui(void) {
    int o = 0;
    if (SendMessageW(g_examples, BM_GETCHECK, 0, 0) == BST_CHECKED) o |= OPT_EXAMPLES;
    if (SendMessageW(g_shortcut, BM_GETCHECK, 0, 0) == BST_CHECKED) o |= OPT_SHORTCUT;
    if (SendMessageW(g_openmods, BM_GETCHECK, 0, 0) == BST_CHECKED) o |= OPT_OPENMODS;
    return o;
}

static void start_job(int op, int preset_opts) {
    if (g_busy) return;
    Job* j = (Job*)calloc(1, sizeof(Job));
    if (!j) return;
    j->op = op;
    get_gd(j->gd);
    j->loader = (int)SendMessageW(g_loader, CB_GETCURSEL, 0, 0);
    if (j->loader < 0) j->loader = 0;
    j->opts = preset_opts >= 0 ? preset_opts : opts_from_ui();

    wchar_t p[PLEN];
    join(p, j->gd, L"GeometryDash.exe");
    if (!is_file(p)) {
        MessageBoxW(g_wnd, L"GeometryDash.exe is not in this folder.", PM_TITLE, MB_ICONWARNING);
        free(j);
        return;
    }
    while (process_running(L"GeometryDash.exe")) {
        if (MessageBoxW(g_wnd, L"Geometry Dash is running. Close the game, then press Retry.", PM_TITLE,
                        MB_RETRYCANCEL | MB_ICONWARNING) != IDRETRY) {
            free(j);
            return;
        }
    }
    if (op == OP_UNINSTALL && preset_opts < 0) {
        int r = MessageBoxW(g_wnd,
                            L"Uninstall PyModder?\n\nAlso delete the pymodder folder with all mods, their saves and logs?\n\n"
                            L"Yes - delete everything\nNo - keep the mods folder\nCancel - do nothing",
                            PM_TITLE, MB_YESNOCANCEL | MB_ICONQUESTION | MB_DEFBUTTON2);
        if (r == IDCANCEL) {
            free(j);
            return;
        }
        if (r == IDYES) j->opts |= OPT_PURGE;
    }
    DWORD e = try_write(j->gd);
    if (e == ERROR_ACCESS_DENIED && !is_elevated()) {
        if (MessageBoxW(g_wnd, L"Administrator rights are needed to change files in the game folder.\n\nRestart the setup as administrator?",
                        PM_TITLE, MB_OKCANCEL | MB_ICONINFORMATION) != IDOK) {
            free(j);
            return;
        }
        wchar_t args[PLEN + 128];
        swprintf(args, PLEN + 128, L"--gd \"%ls\" --loader %d --opts %d --run %ls", j->gd, j->loader, j->opts,
                 op == OP_INSTALL ? L"install" : L"uninstall");
        SHELLEXECUTEINFOW sei;
        memset(&sei, 0, sizeof sei);
        sei.cbSize = sizeof sei;
        sei.lpVerb = L"runas";
        sei.lpFile = g_exe;
        sei.lpParameters = args;
        sei.nShow = SW_SHOWNORMAL;
        free(j);
        if (ShellExecuteExW(&sei)) DestroyWindow(g_wnd);
        else ui_log(L"Administrator rights were not given.");
        return;
    } else if (e) {
        wchar_t m[512], full[PLEN + 600];
        err_text(e, m, 512);
        swprintf(full, PLEN + 600, L"ERROR: cannot write to %ls: %ls.", j->gd, m);
        ui_log(full);
        free(j);
        return;
    }
    InterlockedExchange(&g_busy, 1);
    set_enabled();
    SendMessageW(g_progress, PBM_SETPOS, 0, 0);
    ui_log(L"");
    HANDLE t = CreateThread(NULL, 0, worker, j, 0, NULL);
    if (t) CloseHandle(t);
    else {
        free(j);
        InterlockedExchange(&g_busy, 0);
        set_enabled();
    }
}

static HWND mk(const wchar_t* cls, const wchar_t* text, DWORD style, int x, int y, int w, int h, int id, DWORD ex) {
    HWND c = CreateWindowExW(ex, cls, text, WS_CHILD | WS_VISIBLE | style, S(x), S(y), S(w), S(h), g_wnd,
                             (HMENU)(INT_PTR)id, g_inst, NULL);
    SendMessageW(c, WM_SETFONT, (WPARAM)g_font, TRUE);
    return c;
}

#define W_CLIENT 520
#define H_CLIENT 470

static void create_controls(void) {
    HWND icon = mk(L"STATIC", NULL, SS_ICON | SS_REALSIZECONTROL, 14, 12, 40, 40, ID_ICON, 0);
    HICON big = (HICON)LoadImageW(g_inst, MAKEINTRESOURCEW(1), IMAGE_ICON, S(40), S(40), 0);
    SendMessageW(icon, STM_SETICON, (WPARAM)big, 0);
    HWND t = mk(L"STATIC", L"PyModder 0.7-beta", SS_LEFT, 64, 10, 440, 26, ID_TITLE, 0);
    SendMessageW(t, WM_SETFONT, (WPARAM)g_title_font, TRUE);
    mk(L"STATIC", L"Python mods for Geometry Dash 2.2091", SS_LEFT, 65, 36, 440, 18, ID_SUB, 0);

    mk(L"STATIC", L"Geometry Dash folder:", SS_LEFT, 14, 68, 300, 18, ID_LBL_PATH, 0);
    g_path = mk(L"EDIT", L"", WS_TABSTOP | ES_AUTOHSCROLL, 14, 87, 396, 24, ID_PATH, WS_EX_CLIENTEDGE);
    g_browse = mk(L"BUTTON", L"Browse...", WS_TABSTOP | BS_PUSHBUTTON, 416, 86, 90, 26, ID_BROWSE, 0);
    g_status = mk(L"STATIC", L"", SS_LEFT, 14, 117, 492, 34, ID_STATUS, 0);

    mk(L"STATIC", L"Loader DLL:", SS_LEFT, 14, 161, 80, 18, ID_LBL_LOADER, 0);
    g_loader = mk(L"COMBOBOX", NULL, WS_TABSTOP | CBS_DROPDOWNLIST | WS_VSCROLL, 96, 157, 200, 200, ID_LOADER, 0);
    SendMessageW(g_loader, CB_ADDSTRING, 0, (LPARAM)L"Auto (recommended)");
    for (int i = 0; i < 3; i++) SendMessageW(g_loader, CB_ADDSTRING, 0, (LPARAM)LOADERS[i]);
    SendMessageW(g_loader, CB_SETCURSEL, 0, 0);
    mk(L"STATIC", L"Auto picks a name no other mod uses.", SS_LEFT, 304, 161, 210, 18, ID_HINT, 0);

    g_examples = mk(L"BUTTON", L"Install example mods", WS_TABSTOP | BS_AUTOCHECKBOX, 14, 190, 300, 20, ID_EXAMPLES, 0);
    g_shortcut = mk(L"BUTTON", L"Desktop shortcut to the mods folder", WS_TABSTOP | BS_AUTOCHECKBOX, 14, 212, 300, 20,
                    ID_SHORTCUT, 0);
    g_openmods = mk(L"BUTTON", L"Open the mods folder when done", WS_TABSTOP | BS_AUTOCHECKBOX, 14, 234, 300, 20,
                    ID_OPENMODS, 0);
    SendMessageW(g_examples, BM_SETCHECK, BST_CHECKED, 0);
    SendMessageW(g_shortcut, BM_SETCHECK, BST_CHECKED, 0);
    SendMessageW(g_openmods, BM_SETCHECK, BST_CHECKED, 0);

    g_progress = mk(PROGRESS_CLASSW, NULL, PBS_SMOOTH, 14, 264, 492, 14, ID_PROGRESS, 0);
    SendMessageW(g_progress, PBM_SETRANGE32, 0, 1000);
    g_log = mk(L"EDIT", L"", WS_VSCROLL | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL, 14, 286, 492, 132, ID_LOG,
               WS_EX_CLIENTEDGE);

    g_install = mk(L"BUTTON", L"Install", WS_TABSTOP | BS_DEFPUSHBUTTON, 226, 430, 90, 28, ID_INSTALL, 0);
    g_uninstall = mk(L"BUTTON", L"Uninstall", WS_TABSTOP | BS_PUSHBUTTON, 322, 430, 90, 28, ID_UNINSTALL, 0);
    g_close = mk(L"BUTTON", L"Close", WS_TABSTOP | BS_PUSHBUTTON, 418, 430, 88, 28, ID_CLOSE, 0);
}

static LRESULT CALLBACK wnd_proc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    switch (m) {
    case WM_COMMAND:
        switch (LOWORD(wp)) {
        case ID_BROWSE: browse(); return 0;
        case ID_INSTALL:
        case ID_UNINSTALL: {
            int o = g_preset_opts;
            g_preset_opts = -1;
            start_job(LOWORD(wp) == ID_INSTALL ? OP_INSTALL : OP_UNINSTALL, o);
            return 0;
        }
        case ID_CLOSE:
        case IDCANCEL: PostMessageW(h, WM_CLOSE, 0, 0); return 0;
        case ID_PATH:
            if (HIWORD(wp) == EN_CHANGE) SetTimer(h, 1, 300, NULL);
            return 0;
        case ID_LOADER:
            if (HIWORD(wp) == CBN_SELCHANGE) update_status();
            return 0;
        }
        break;
    case WM_TIMER:
        KillTimer(h, wp);
        update_status();
        return 0;
    case WM_CTLCOLORSTATIC: {
        HDC dc = (HDC)wp;
        HWND c = (HWND)lp;
        if (c == g_log) {
            SetBkColor(dc, GetSysColor(COLOR_WINDOW));
            SetTextColor(dc, GetSysColor(COLOR_WINDOWTEXT));
            return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
        }
        SetBkColor(dc, GetSysColor(COLOR_WINDOW));
        SetTextColor(dc, c == g_status ? g_status_color : GetSysColor(COLOR_WINDOWTEXT));
        return (LRESULT)GetSysColorBrush(COLOR_WINDOW);
    }
    case WM_APP_LOG: {
        wchar_t* s = (wchar_t*)lp;
        ui_log(s);
        free(s);
        return 0;
    }
    case WM_APP_PROGRESS:
        SendMessageW(g_progress, PBM_SETPOS, (WPARAM)MulDiv((int)wp, 1000, (int)lp > 0 ? (int)lp : 1), 0);
        return 0;
    case WM_APP_DONE:
        InterlockedExchange(&g_busy, 0);
        update_status();
        if (wp) SetFocus(g_close);
        MessageBeep(wp ? MB_OK : MB_ICONERROR);
        return 0;
    case WM_CLOSE:
        if (g_busy) {
            MessageBeep(MB_ICONWARNING);
            return 0;
        }
        DestroyWindow(h);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(h, m, wp, lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show) {
    (void)prev;
    (void)cmdline;
    g_inst = inst;
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    INITCOMMONCONTROLSEX icc = {sizeof icc, ICC_PROGRESS_CLASS | ICC_STANDARD_CLASSES};
    InitCommonControlsEx(&icc);

    GetModuleFileNameW(NULL, g_exe, PLEN);
    wcscpy(g_src, g_exe);
    wchar_t* sl = wcsrchr(g_src, L'\\');
    if (sl) *sl = 0;
    wcscat(g_src, L"\\files");
    {
        wchar_t a[PLEN], b[PLEN], c[PLEN];
        join(a, g_src, L"pymodder");
        join(b, a, L"core");
        join(a, g_src, L"loaders");
        join(c, a, L"XInput1_4.dll");
        g_have_files = is_dir(b) && is_file(c);
    }

    HDC dc = GetDC(NULL);
    g_dpi = GetDeviceCaps(dc, LOGPIXELSY);
    ReleaseDC(NULL, dc);
    NONCLIENTMETRICSW ncm;
    ncm.cbSize = sizeof ncm;
    SystemParametersInfoW(SPI_GETNONCLIENTMETRICS, sizeof ncm, &ncm, 0);
    g_font = CreateFontIndirectW(&ncm.lfMessageFont);
    LOGFONTW lf = ncm.lfMessageFont;
    lf.lfHeight = -MulDiv(15, g_dpi, 72);
    lf.lfWeight = FW_BOLD;
    g_title_font = CreateFontIndirectW(&lf);

    WNDCLASSEXW wc;
    memset(&wc, 0, sizeof wc);
    wc.cbSize = sizeof wc;
    wc.lpfnWndProc = wnd_proc;
    wc.hInstance = inst;
    wc.hIcon = LoadIconW(inst, MAKEINTRESOURCEW(1));
    wc.hIconSm = (HICON)LoadImageW(inst, MAKEINTRESOURCEW(1), IMAGE_ICON, GetSystemMetrics(SM_CXSMICON),
                                   GetSystemMetrics(SM_CYSMICON), 0);
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.hbrBackground = GetSysColorBrush(COLOR_WINDOW);
    wc.lpszClassName = L"PyModderSetup";
    RegisterClassExW(&wc);

    DWORD style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
    RECT r = {0, 0, S(W_CLIENT), S(H_CLIENT)};
    AdjustWindowRect(&r, style, FALSE);
    int ww = r.right - r.left, wh = r.bottom - r.top;
    RECT wa;
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &wa, 0);
    g_wnd = CreateWindowExW(0, wc.lpszClassName, PM_TITLE, style, wa.left + (wa.right - wa.left - ww) / 2,
                            wa.top + (wa.bottom - wa.top - wh) / 2, ww, wh, NULL, NULL, inst, NULL);
    if (!g_wnd) return 1;
    create_controls();

    // command line
    int argc = 0, run = 0, loader = 0, opts = -1;
    wchar_t gd[PLEN] = L"";
    wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    for (int i = 1; argv && i < argc; i++) {
        if (!wcscmp(argv[i], L"--gd") && i + 1 < argc) wcsncpy(gd, argv[++i], PLEN - 1);
        else if (!wcscmp(argv[i], L"--loader") && i + 1 < argc) loader = _wtoi(argv[++i]);
        else if (!wcscmp(argv[i], L"--opts") && i + 1 < argc) opts = _wtoi(argv[++i]);
        else if (!wcscmp(argv[i], L"--run") && i + 1 < argc) {
            i++;
            run = !wcscmp(argv[i], L"install") ? OP_INSTALL : !wcscmp(argv[i], L"uninstall") ? OP_UNINSTALL : 0;
        } else if (i == 1 && argv[i][0] != L'-') wcsncpy(gd, argv[i], PLEN - 1);
    }
    if (argv) LocalFree(argv);
    if (loader < 0 || loader > 3) loader = 0;
    SendMessageW(g_loader, CB_SETCURSEL, loader, 0);
    if (opts >= 0) {
        SendMessageW(g_examples, BM_SETCHECK, (opts & OPT_EXAMPLES) ? BST_CHECKED : BST_UNCHECKED, 0);
        SendMessageW(g_shortcut, BM_SETCHECK, (opts & OPT_SHORTCUT) ? BST_CHECKED : BST_UNCHECKED, 0);
        SendMessageW(g_openmods, BM_SETCHECK, (opts & OPT_OPENMODS) ? BST_CHECKED : BST_UNCHECKED, 0);
    }

    ui_log(L"PyModder " PM_VERSION L" setup.");
    wchar_t found[PLEN];
    if (gd[0]) {
        clean_path(gd);
        SetWindowTextW(g_path, gd);
    } else if (find_gd(found)) {
        SetWindowTextW(g_path, found);
        wchar_t m[PLEN + 64];
        swprintf(m, PLEN + 64, L"Found Geometry Dash: %ls", found);
        ui_log(m);
    } else {
        ui_log(L"Geometry Dash was not found automatically: press Browse... and choose its folder.");
    }
    if (!g_have_files) {
        ui_log(L"");
        ui_log(L"The \"files\" folder is missing next to PyModder Setup.exe, so only Uninstall works.");
        ui_log(L"Extract the whole zip first (right click > Extract All...), then run PyModder Setup.exe from there.");
    }
    KillTimer(g_wnd, 1);
    update_status();
    ShowWindow(g_wnd, show);
    UpdateWindow(g_wnd);
    SetFocus(g_have_files ? g_install : g_browse);
    if (run) {
        g_preset_opts = opts;
        PostMessageW(g_wnd, WM_COMMAND, run == OP_INSTALL ? ID_INSTALL : ID_UNINSTALL, 0);
    }

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        if (!IsDialogMessageW(g_wnd, &msg)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
    CoUninitialize();
    return 0;
}
