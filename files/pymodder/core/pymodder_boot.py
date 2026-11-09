"""PyModder: started by the loader DLL (XInput1_4.dll / opengl32.dll / version.dll) inside Geometry Dash."""
import faulthandler
import json
import os
import sys
import time


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass

    def flush(self):
        pass


def main(root, log):
    cfg_path = os.path.join(root, 'config.json')
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            cfg = json.load(open(cfg_path, encoding='utf-8-sig'))
        except Exception as e:
            print('[PyModder] config.json:', e)
    if cfg.get('console'):
        import ctypes
        ctypes.windll.kernel32.AllocConsole()
        con = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
        sys.stdout = sys.stderr = _Tee(log, con)
    faulthandler.enable(log, all_threads=True)
    print('[PyModder] %s  Python %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), sys.version.split()[0]))
    from gd import _core
    _core.start(root, cfg)
