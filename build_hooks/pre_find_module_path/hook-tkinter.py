def pre_find_module_path(hook_api):
    """
    Override local para no excluir `tkinter` en entornos donde PyInstaller
    detecta mal Tcl/Tk dentro de una venv de Windows.
    """
    return None
