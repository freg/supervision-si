# -*- coding: utf-8 -*-
"""Lancement d'une application dans la session de l'utilisateur ouverte sur la
console Windows (livraison #683).

L'agent tourne en service (SYSTEM, session 0) : un programme lancé par un simple
Popen y reste invisible -- défaut vu au campus sur le chien de garde #613. Ici :
jeton de l'utilisateur de la session console (WTSQueryUserToken, réservé à
SYSTEM), bloc d'environnement de cet utilisateur, CreateProcessAsUserW sur le
bureau « winsta0\\default ». La commande passe par `cmd /c start` (fenêtre de cmd
masquée) pour garder la syntaxe libre du champ « commande de relance ».

`command_line` est pure (testée partout) ; `spawn_in_console` ne fonctionne que
sous Windows.
"""
import os

NO_SESSION = 0xFFFFFFFF
CREATE_NO_WINDOW = 0x08000000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NEW_PROCESS_GROUP = 0x00000200
ERROR_NO_TOKEN = 1008


def command_line(command, cwd=None, comspec=None):
    """-> ligne de commande `cmd.exe /d /c start "" [/D "cwd"] <commande>`. Pure."""
    comspec = comspec or os.environ.get("ComSpec") or r"C:\Windows\System32\cmd.exe"
    parts = ['"%s"' % comspec, "/d", "/c", "start", '""']
    if cwd:
        parts += ["/D", '"%s"' % str(cwd).strip('"')]
    parts.append(command)
    return " ".join(parts)


def current_session_id():
    """Session du processus courant (0 = services), None hors Windows."""
    try:
        import ctypes
        from ctypes import wintypes
        sid = wintypes.DWORD()
        if ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid)):
            return sid.value
    except (ImportError, AttributeError, OSError):
        pass
    return None


def spawn_in_console(command, cwd=None):
    """-> (ok, erreur, session). Lance `command` dans la session console active."""
    import ctypes
    from ctypes import wintypes

    k32, wts, adv, env = (ctypes.WinDLL(n, use_last_error=True) for n in ("kernel32", "wtsapi32", "advapi32", "userenv"))
    k32.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                    ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                    ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
                    ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                    ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]

    session = k32.WTSGetActiveConsoleSessionId()
    if session == NO_SESSION:
        return False, "aucune session sur la console", None
    token = wintypes.HANDLE()
    if not wts.WTSQueryUserToken(wintypes.ULONG(session), ctypes.byref(token)):
        err = ctypes.get_last_error()
        if err == ERROR_NO_TOKEN:
            return False, "aucun utilisateur connecté sur la console (session %d)" % session, session
        return False, "jeton de la session %d inaccessible (erreur %d, agent hors SYSTEM ?)" % (session, err), session
    block = ctypes.c_void_p()
    try:
        if not env.CreateEnvironmentBlock(ctypes.byref(block), token, False):
            block = ctypes.c_void_p()
        si = STARTUPINFO()
        si.cb = ctypes.sizeof(si)
        si.lpDesktop = "winsta0\\default"
        pi = PROCESS_INFORMATION()
        cmdline = ctypes.create_unicode_buffer(command_line(command, cwd))
        flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | (CREATE_UNICODE_ENVIRONMENT if block else 0)
        ok = adv.CreateProcessAsUserW(token, None, cmdline, None, None, False, flags, block,
                                      cwd or None, ctypes.byref(si), ctypes.byref(pi))
        if not ok:
            return False, "CreateProcessAsUser : erreur %d" % ctypes.get_last_error(), session
        k32.CloseHandle(pi.hThread)
        k32.CloseHandle(pi.hProcess)
        return True, None, session
    finally:
        if block:
            env.DestroyEnvironmentBlock(block)
        k32.CloseHandle(token)
