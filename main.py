import webview
import os
import sys

def get_resource_path(relative_path):
    """ Obtén a ruta absoluta para os recursos, compatible con PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)

index_html = get_resource_path(os.path.join('web', 'dist', 'index.html'))

window = webview.create_window('BlackVault', index_html)
webview.start()