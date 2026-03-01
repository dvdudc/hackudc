import { app, BrowserWindow, ipcMain, screen, shell, globalShortcut } from 'electron'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn, ChildProcess } from 'node:child_process'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// The built directory structure
//
// ├─┬─┬ dist
// │ │ └── index.html
// │ │
// │ ├─┬ dist-electron
// │ │ ├── main.js
// │ │ └── preload.mjs
// │
process.env.APP_ROOT = path.join(__dirname, '..')

// 🚧 Use ['ENV_NAME'] avoid vite:define plugin - Vite@2.x
export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL']
export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist-electron')
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist')

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, 'public') : RENDERER_DIST

let win: BrowserWindow | null = null
let apiProcess: ChildProcess | null = null
// Lowered widget size for a smaller footprint
const WIDGET_SIZE = 140

function startBackendApi() {
    if (app.isPackaged) {
        console.log("Running in packaged mode. Assuming API is already started by blackvault_run.bat");
        return;
    }

    const appRoot = process.env.APP_ROOT as string;
    const apiPath = path.join(appRoot, '..', 'src', 'api.py');
    console.log('Starting Python backend at:', apiPath);

    // Use the venv python if it exists, fallback to global python
    const pythonExecutable = process.platform === 'win32'
        ? path.join(appRoot, '..', '.venv', 'Scripts', 'python.exe')
        : path.join(appRoot, '..', '.venv', 'bin', 'python');

    apiProcess = spawn(pythonExecutable, [apiPath], {
        cwd: path.join(appRoot, '..'),
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    apiProcess.stdout?.on('data', (data) => {
        console.log(`API: ${data}`);
    });

    apiProcess.stderr?.on('data', (data) => {
        console.error(`API Error: ${data}`);
    });
}

function createWindow() {
    const primaryDisplay = screen.getPrimaryDisplay()
    const { width, height } = primaryDisplay.workAreaSize

    win = new BrowserWindow({
        icon: path.join((process.env.VITE_PUBLIC as string) || '', 'electron-vite.svg'),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: true,
            contextIsolation: true, // Required for secure IPC preload bridge
        },
        width: WIDGET_SIZE,
        height: WIDGET_SIZE,
        x: width - WIDGET_SIZE - 20, // pinned to right
        y: height - WIDGET_SIZE - 20, // pinned to bottom
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        resizable: false,
    })

    // Test active push message to Renderer-process.
    win.webContents.on('did-finish-load', () => {
        win?.webContents.send('main-process-message', (new Date).toLocaleString())
    })

    // Let the window ignore mouse events if the pixel is fully transparent 
    // This allows clicking through the widget background while keeping the BlackHole solid.
    // Note: requires setting this true initially sometimes but we use a specialized approach.
    win.setIgnoreMouseEvents(false); // We start false, and will let drag regions handle the top. 

    if (VITE_DEV_SERVER_URL) {
        win.loadURL(VITE_DEV_SERVER_URL)
    } else {
        // win.loadFile('dist/index.html')
        win.loadFile(path.join(RENDERER_DIST, 'index.html'))
    }
}

// IPC Handlers
ipcMain.on("window-expand", () => {
    if (win) {
        // Expand to left, keep bottom-right anchor
        const primaryDisplay = screen.getPrimaryDisplay()
        const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize

        const expandedWidth = 800;
        const expandedHeight = 600;

        win.setResizable(true);
        win.setBounds({
            x: screenWidth - expandedWidth - 20,
            y: screenHeight - expandedHeight - 20,
            width: expandedWidth,
            height: expandedHeight
        }, true);
    }
})

ipcMain.on("window-shrink", () => {
    if (win) {
        // Shrink back down to widget size
        const primaryDisplay = screen.getPrimaryDisplay()
        const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize

        win.setBounds({
            x: screenWidth - WIDGET_SIZE - 20,
            y: screenHeight - WIDGET_SIZE - 20,
            width: WIDGET_SIZE,
            height: WIDGET_SIZE
        })
        win.setResizable(false);
    }
})

ipcMain.on("window-expand-input", () => {
    if (win) {
        // Expand slightly to show the input box on the left
        const primaryDisplay = screen.getPrimaryDisplay()
        const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize

        const inputWidth = 400; // Enough space for the input box
        win.setResizable(true);
        win.setBounds({
            x: screenWidth - inputWidth - 20,
            y: screenHeight - WIDGET_SIZE - 20,
            width: inputWidth,
            height: WIDGET_SIZE
        });
    }
})

import fs from 'node:fs';
import { nativeImage } from 'electron';

ipcMain.on("drag-out", (event, filePath: string) => {
    try {
        // The DB might send paths with literal '...' in them (like C:\Users\...\file.txt)
        // or relative paths. We must extract just the filename and rebuild the correct path
        // pointing to the blackvault_data/files directory.
        const appRoot = process.env.APP_ROOT as string;
        const vaultFilesDir = path.join(appRoot, '..', 'blackvault_data', 'files');
        const fileNameParts = filePath.replace(/\\/g, '/').split('/');
        const fileName = fileNameParts[fileNameParts.length - 1];
        const absolutePath = path.join(vaultFilesDir, fileName);

        console.log("======================");
        console.log(`[Drag Out Debug] Raw filePath string received: "${filePath}"`);
        console.log(`[Drag Out Debug] Parts array: ${JSON.stringify(fileNameParts)}`);
        console.log(`[Drag Out Debug] Extracted fileName: "${fileName}"`);
        console.log(`[Drag Out Debug] Rebuilt absolute path: "${absolutePath}"`);
        console.log(`[Drag Out Debug] fs.existsSync result: ${fs.existsSync(absolutePath)}`);
        console.log("======================");

        if (!fs.existsSync(absolutePath)) {
            console.error(`❌ Drag out failed: file no longer exists on disk: "${absolutePath}"`);
            event.sender.send("drag-out-error", `El archivo buscado ya no existe en el Vault y no se puede extraer.\nRuta buscada: ${absolutePath}`);
            return;
        }

        // Use a solid RED icon resized to 32x32 so the user actually sees they are dragging something!
        const icon = nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==').resize({ width: 32, height: 32 });

        event.sender.startDrag({
            file: absolutePath,
            icon: icon,
        });
        console.log(`[Drag Out] Successfully started drag for: ${absolutePath}`);
    } catch (err) {
        console.error("❌ Drag out exception:", err);
    }
})

ipcMain.on("open-file", async (event, filePath: string) => {
    try {
        const appRoot = process.env.APP_ROOT as string;
        const vaultFilesDir = path.join(appRoot, '..', 'blackvault_data', 'files');
        const fileNameParts = filePath.replace(/\\/g, '/').split('/');
        const fileName = fileNameParts[fileNameParts.length - 1];
        const absolutePath = path.join(vaultFilesDir, fileName);

        console.log("======================");
        console.log(`[Open File Debug] Raw filePath string received: "${filePath}"`);
        console.log(`[Open File Debug] Parts array: ${JSON.stringify(fileNameParts)}`);
        console.log(`[Open File Debug] Extracted fileName: "${fileName}"`);
        console.log(`[Open File Debug] Rebuilt absolute path: "${absolutePath}"`);
        console.log(`[Open File Debug] fs.existsSync result: ${fs.existsSync(absolutePath)}`);
        console.log("======================");
        if (!fs.existsSync(absolutePath)) {
            console.error(`❌ Open file failed: file no longer exists on disk: ${absolutePath}`);
            event.sender.send("drag-out-error", "El archivo ya no existe en el disco.");
            return;
        }
        await shell.openPath(absolutePath);
    } catch (err) {
        console.error("❌ Open file exception:", err);
    }
})

ipcMain.on("window-close", () => {
    if (win) {
        win.close();
    }
    app.quit()
})

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
    if (apiProcess) {
        apiProcess.kill();
    }
    if (process.platform !== 'darwin') {
        app.quit()
        win = null
    }
})

app.on('quit', () => {
    if (apiProcess) {
        apiProcess.kill();
    }
})

app.on('will-quit', () => {
    globalShortcut.unregisterAll()
})

app.on('activate', () => {
    // On OS X it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow()
    }
})

app.whenReady().then(() => {
    startBackendApi()
    createWindow()

    // Global Shortcuts
    globalShortcut.register('CommandOrControl+Shift+B', () => {
        if (win) {
            if (win.isVisible()) {
                win.hide()
            } else {
                win.show()
                win.focus()
            }
        }
    })

    globalShortcut.register('CommandOrControl+Shift+Space', () => {
        if (win) {
            if (!win.isVisible()) {
                win.show()
            }
            win.focus()
            // Tell React to expand the window and focus the search box
            win.webContents.send('shortcut-expand-search')
        }
    })
})
